use std::collections::HashMap;

struct Foo;

impl Foo {
    fn bar(&self, x: i32) -> i32 {
        helper(x)
    }
}

fn helper(x: i32) -> i32 {
    x + 1
}
