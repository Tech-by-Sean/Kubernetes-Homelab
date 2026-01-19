extension = str(input('What is the name of your file? '))

if extension == ['.gif, .jpg, .jpeg, .png, .pdf, .txt, .zip']:
    print(extension)
else:
    print('application/octet-stream')