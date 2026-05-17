#!/bin/bash
# Downloads stockfish.js (WebAssembly build) into the extension directory.
# Run once: bash chess_extension/get_stockfish.sh

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Downloading stockfish.js..."
curl -fsSL "https://unpkg.com/stockfish/src/stockfish-nnue-16-single.js" -o "$DIR/stockfish.js"
echo "Done — stockfish.js saved to chess_extension/"
