package com.example;

import java.util.List;

public class Foo {
    public int bar(int x) {
        return Helper.help(x);
    }
}

class Helper {
    static int help(int x) {
        return x + 1;
    }
}
