
def calculator():

    x = float(input("What is X: "))
    operation = input("Enter operation (+, -, *, /, //, %): ")
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