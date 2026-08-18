#!/usr/bin/env sh
set -eu

printf 'Node.js: '
node --version
printf 'npm: '
npm --version
printf '%s\n' 'Installing the exact dependency versions from package-lock.json...'

npm ci

printf '%s\n' 'Setup complete. Start the app with: npm run dev'
