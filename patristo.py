def text_clean(text, LETTERS='ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    text_upper=text.upper()
    cleaned_text=''
    for char in text_upper:
        if char in LETTERS:
            cleaned_text+=char
    return cleaned_text

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
        plaintext_num = LETTERS.find(i)
        plaintext+=cipher[plaintext_num]
    return plaintext
