def main():
    x = fraction('Fraction: ')
    print(x)

def fraction(prompt):
    while True:
        try:
            user_input = input(prompt)
            x, y = user_input.split('/')
            x = int(x)
            y = int(y)

            if x > y:
                continue

            percentage = (x / y) * 100
            if percentage >= 99:
                return 'F'
            elif percentage <= 1:
                return 'E'
            else:
                return f'{round(percentage)}%'
        except (ValueError, ZeroDivisionError):
            pass
main()