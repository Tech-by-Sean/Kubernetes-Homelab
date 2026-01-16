def grade():

    score1 = int(input('score 1: '))
    score2 = int(input('score 2: '))
    score3 = int(input('score 3: '))
    score4 = int(input('score 4: '))

    score = (score1 + score2 + score3 + score4) / 4

    if score >= 90:
        print(f'{score} is equal to A')
    elif score >= 80:
        print(f'{score} is equal to B')
    elif score >= 70:
        print(f'{score} is equal to C')
    elif score >= 60:
        print(f'{score} is equal to D')
    else:
        print(f'{score} is equal to F')
    
grade()