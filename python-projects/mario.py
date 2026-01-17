def main():
    print_row(3)

def print_row(width):
    for i in range(width):
        print_height(width)

def print_height(height):
    print('#' * height)
    

main()