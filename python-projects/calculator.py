
def calculator():

    x = float(input("What is X: "))
    operation: str = input("Enter operation (+, -, *, /, //, %): ")
    y = float(input("What is Y: "))

    if (operation == '+'):
        print(x + y)
    
    elif (operation == '-'):
        print(x - y)
    
    elif (operation == '*'):
        print(x * y)
    
    elif (operation == '/'):
        print(x / y)
    
    elif (operation == '//'):
        print(x // y)
    
    elif (operation == '%'):
        print(x % y)

    else:
        print("Invalid operation")

calculator()