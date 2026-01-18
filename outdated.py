months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
]

user_input = input('Date: ')

if '/' in user_input:
    user_input = user_input.split('/')
    month = int(user_input[0])
    day = int(user_input[1])
    year = int(user_input[2])
    if 1 <= month <= 12 and 1 <= day <= 31:
        print(f'{year}-{month:02}-{day:02}')    
    
for month_name in months:
    if month_name in user_input:
        parts = user_input.split(' ')
        day = int(parts[1].replace(',', ''))
        year = int(parts[2])
        month = months.index(month_name) + 1
        if 1 <= month <= 12 and 1 <= day <= 31:
            print(f'{year}-{month:02}-{day:02}')
