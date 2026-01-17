def greetfailure():

    greeting = str(input('Greeting: '))

    if greeting == 'hello':
        print('$0')

    elif 'h' in greeting:
        print('$20')

    else:
        print('$100')

greetfailure()