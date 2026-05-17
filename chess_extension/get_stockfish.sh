#!/bin/bash
# Downloads stockfish.js (WebAssembly build) into the extension directory.
# Run once: bash chess_extension/get_stockfish.sh

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Downloading stockfish.js (~1.5 MB, single-file build for browsers)..."
curl -fsSL "https://cdn.jsdelivr.net/npm/stockfish.js@10.0.2/stockfish.js" -o "$DIR/stockfish.js"
echo "Done — stockfish.js saved to chess_extension/"
