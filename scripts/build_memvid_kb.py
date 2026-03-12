#!/usr/bin/env python3
"""
Build Memvid Knowledge Base for RAG Integration

Usage:
    python scripts/build_memvid_kb.py --input specs/ --output drs_knowledge.mp4
"""

import argparse
import logging
from pathlib import Path

from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Memvid
from FlagEmbedding import FlagModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_kb(input_dir: str, output: str, chunk_size: int = 512, chunk_overlap: int = 50):
    """
    Build knowledge base from markdown files.
    
    Args:
        input_dir: Directory containing markdown specifications
        output: Output path for Memvid knowledge base (.mp4)
        chunk_size: Size of text chunks (default 512 tokens)
        chunk_overlap: Overlap between chunks (default 50 tokens)
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    logger.info(f"Loading documents from {input_dir}...")
    loader = DirectoryLoader(input_dir, glob="**/*.md", show_progress=True)
    docs = loader.load()
    logger.info(f"Loaded {len(docs)} documents")
    
    logger.info("Splitting documents into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Created {len(chunks)} chunks")
    
    # Add metadata for source tracking
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
        chunk.metadata["doc_id"] = chunk.metadata.get("source", "unknown")
    
    logger.info("Initializing bge-m3 embedder...")
    embedder = FlagModel('BAAI/bge-m3', use_fp16=True)
    
    logger.info("Building Memvid knowledge base...")
    kb = Memvid.from_documents(chunks, embedder)
    
    logger.info(f"Saving knowledge base to {output}...")
    kb.save(output)
    
    logger.info(f"✅ Knowledge base built successfully!")
    logger.info(f"  - Documents: {len(docs)}")
    logger.info(f"  - Chunks: {len(chunks)}")
    logger.info(f"  - Output: {output}")
    logger.info(f"  - Size: {Path(output).stat().st_size / 1024 / 1024:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Build Memvid knowledge base for DRS")
    parser.add_argument(
        "--input",
        type=str,
        default="docs/",
        help="Input directory containing markdown files (default: docs/)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="drs_knowledge.mp4",
        help="Output path for knowledge base (default: drs_knowledge.mp4)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in tokens (default: 512)"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Chunk overlap in tokens (default: 50)"
    )
    
    args = parser.parse_args()
    
    try:
        build_kb(
            input_dir=args.input,
            output=args.output,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )
    except Exception as e:
        logger.error(f"❌ Failed to build knowledge base: {e}")
        raise


if __name__ == "__main__":
    main()
