students = [
    {"name": "Harry Potter", "house": "Gryffindor", "patronus": "Stag"},
    {"name": "Hermione Granger", "house": "Gryffindor", "patronus": "Otter"},
    {"name": "Ron Weasley", "house": "Gryffindor", "patronus": "Jack Russell Terrier"},
    {"name": "Luna Lovegood", "house": "Ravenclaw", "patronus": "Hare"},
    {"name": "Cho Chang", "house": "Ravenclaw", "patronus": "Swan"},
    {"name": "Cedric Diggory", "house": "Hufflepuff", "patronus": "Unknown"},
    {"name": "Nymphadora Tonks", "house": "Hufflepuff", "patronus": "Jack Rabbit"},
    {"name": "Draco Malfoy", "house": "Slytherin", "patronus": "Unknown"},
    {"name": "Severus Snape", "house": "Slytherin", "patronus": "Doe"},
    {"name": "Ginny Weasley", "house": "Gryffindor", "patronus": "Horse"},
    {"name": "Neville Longbottom", "house": "Gryffindor", "patronus": "Unknown"},
    {"name": "Seamus Finnigan", "house": "Gryffindor", "patronus": "Fox"},
    {"name": "Ernie Macmillan", "house": "Hufflepuff", "patronus": "Boar"},
    {"name": "Kingsley Shacklebolt", "house": "Unknown", "patronus": "Lynx"},
    {"name": "Remus Lupin", "house": "Gryffindor", "patronus": "Wolf"}
]

for student in students:
    print(student['name'], student['house'], sep= ': ')