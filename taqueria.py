

items = {
    "Baja Taco": 4.25,
    "Burrito": 7.50,
    "Bowl": 8.50,
    "Nachos": 11.00,
    "Quesadilla": 8.50,
    "Super Burrito": 8.50,
    "Super Quesadilla": 9.50,
    "Taco": 3.00,
    "Tortilla Salad": 8.00
    }

running_total = 0 

while True:
    try:
        order = input('What would you like to order? ')
        order = order.title()
        if order in items:
            running_total += items[order]
            print (f'${running_total:.2f}')
    except EOFError:
        print('\nThank you for your order :)')                    
        break