use anyhow::{Context, Result};
use crossbeam_channel::{Receiver, bounded};
use futures::stream::{self, StreamExt};
use std::thread;

pub type ReadResult = (String, Vec<u8>);

pub fn fast_readfiles(
    files: Vec<String>,
    limit: usize,
    threads: usize,
) -> Receiver<Result<ReadResult>> {
    let num_threads = if threads == 0 { 1 } else { threads };

    let core_ids = core_affinity::get_core_ids().unwrap_or_default();

    let (sender, receiver) = bounded(4096);

    let mut chunks: Vec<Vec<String>> = (0..num_threads).map(|_| Vec::new()).collect();
    for (i, file) in files.into_iter().enumerate() {
        chunks[i % num_threads].push(file);
    }

    for (i, file_chunk) in chunks.into_iter().enumerate() {
        if file_chunk.is_empty() {
            continue;
        }

        let thread_sender = sender.clone();
        let core_id = core_ids.get(i % core_ids.len()).copied();

        thread::spawn(move || {
            if let Some(id) = core_id {
                core_affinity::set_for_current(id);
            }

            let mut rt = monoio::RuntimeBuilder::<monoio::FusionDriver>::new()
                .enable_all()
                .with_entries(1024)
                .build()
                .expect("Failed to create monoio runtime");

            rt.block_on(async move {
                let file_stream = stream::iter(file_chunk.into_iter());

                const PER_THREAD_CONCURRENCY: usize = 32;

                file_stream
                    .for_each_concurrent(PER_THREAD_CONCURRENCY, |path| {
                        let sender = thread_sender.clone();
                        async move {
                            let res = read_one_file_buffered(&path, limit).await;

                            let send_data = res.map(|data| (path.clone(), data));

                            let _ = sender.send(send_data);
                        }
                    })
                    .await;
            });
        });
    }

    drop(sender);
    receiver
}

async fn read_one_file_buffered(path: &str, requested_size: usize) -> Result<Vec<u8>> {
    let f = monoio::fs::File::open(path)
        .await
        .with_context(|| format!("Failed to open file: {}", path))?;

    let metadata = f.metadata().await?;
    let file_len = metadata.len() as usize;

    let read_len = if requested_size > 0 && requested_size < file_len {
        requested_size
    } else {
        file_len
    };

    if read_len == 0 {
        return Ok(vec![]);
    }

    let buffer = vec![0u8; read_len];

    let (res, buffer) = f.read_exact_at(buffer, 0).await;

    match res {
        Ok(_) => Ok(buffer),
        Err(e) => Err(anyhow::Error::new(e).context(format!("Failed to read file: {}", path))),
    }
}
