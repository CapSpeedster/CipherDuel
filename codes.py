def text_clean(text, LETTERS='ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    text_upper=text.upper()
    cleaned_text=''
    for char in text_upper:
        if char in LETTERS:
            cleaned_text+=char
    return cleaned_text

def text_block(text, n=5):
    blocked_text = ''
    counter = 0
    
    for char in text:
        blocked_text += char
        counter += 1
        if counter % 5 == 0:
            blocked_text += ' '
    
    return blocked_text.strip()

def form_cipher(key, shift, LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    cipher = key+LETTERS
    result=[]
    seen=set()
    for char in cipher:
        if char not in seen:
            result.append(char)
            seen.add(char)
    return''.join(result)[shift:] + ''.join(result)[:shift] 

def patristok1(text, key, shift, LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    text=text_clean(text)
    cipher=form_cipher(text_clean(key), shift)
    plaintext=''
    for i in text:
        ciphertext_num = cipher.find(i)
        plaintext+=LETTERS[ciphertext_num]
    return text_block(plaintext)

def patristok2(text, key, shift, LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    text = text_clean(text)
    cipher = form_cipher(text_clean(key), shift)
    plaintext=''
    for i in text:
        plaintext_num = LETTERS.find(i)
        plaintext+=cipher[plaintext_num]
    return text_block(plaintext)

def get_frequency(text, LETTERS='ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    frequency = []
    
    for char in LETTERS:
        count = 0
        for i in text_clean(text):
            if char==i:
                count+=1
        frequency.append(count)
    
    return frequency

def nihilist(text, polykey, regkey, LETTERS='ABCDEFGHIKLMNOPQRSTUVWXYZ', replaced_letter='J', replacing_letter='I'):
    text = text_clean(text)
    polykey = text_clean(polykey)
    regkey = text_clean(regkey)
    replaced_letter = text_clean(replaced_letter)
    replacing_letter = text_clean(replacing_letter)
    text=text.replace(replaced_letter,replacing_letter)
    polykey=polykey.replace(replaced_letter, replacing_letter)
    regkey=regkey.replace(replaced_letter, replacing_letter)
    keystring = form_cipher(polykey,0,LETTERS)
    numVals = [11,12,13,14,15,21,22,23,24,25,31,32,33,34,35,41,42,43,44,45,51,52,53,54,55]
    midtext=[]
    key=[]
    plaintext=[]

    for i in text:
        ciphertext_num = keystring.find(i)
        midtext.append(numVals[ciphertext_num])
    
    print(midtext)
    

    for i in regkey:
        ciphertext_num = keystring.find(i)
        key.append(numVals[ciphertext_num])
    
    for i in range(len(text)):
        plaintext.append(midtext[i]+key[i%len(key)])
    
    return plaintext
    
