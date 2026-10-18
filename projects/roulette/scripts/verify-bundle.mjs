import { statSync } from 'node:fs';
import assert from 'node:assert/strict';
import console from 'node:console';
const artifact = 'today-lunch-roulette.ait';
const size = statSync(artifact).size;
assert(size > 0, 'AIT artifact must not be empty');
console.log(`${artifact}: ${size.toLocaleString()} bytes (verified)`);
