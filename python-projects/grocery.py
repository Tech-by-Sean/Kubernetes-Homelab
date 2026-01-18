import time

print('Grocery list')
time.sleep(1)
print('Please enter your list.')
time.sleep(2)

counter = 1
user_data_list = {}



while True:
    try:
        item = input(f'Item {counter}: ')
        item = item.lower()
        if item in user_data_list:
                user_data_list[item] = user_data_list[item] + 1
        else:
            user_data_list[item] = 1
        counter += 1
    except EOFError:
        print()
        break
    
for item in sorted(user_data_list):
    print(f'{user_data_list[item]} {item.upper()}')
        

