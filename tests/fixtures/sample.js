const fs = require('fs');
import { readFile } from 'fs';

class Foo {
    bar(x) {
        return helper(x);
    }
}

function helper(x) {
    return fs.existsSync(x);
}

const arrow = (x) => helper(x);
