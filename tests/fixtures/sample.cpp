#include <iostream>

int helper(int x) {
    return x + 1;
}

class Foo {
public:
    int bar(int x) {
        return helper(x);
    }
};
