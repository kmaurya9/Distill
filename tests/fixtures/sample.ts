import { readFile } from 'fs';

class Foo {
    bar(x: number): number {
        return helper(x);
    }
}

function helper(x: number): number {
    return x + 1;
}

const arrow = (x: number) => helper(x);
