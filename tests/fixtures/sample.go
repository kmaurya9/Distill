package main

import "fmt"

type Foo struct{}

func (f Foo) Bar(x int) int {
    return helper(x)
}

func helper(x int) int {
    return x + 1
}

func main() {
    fmt.Println(helper(1))
}
