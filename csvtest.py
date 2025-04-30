import csv

# Open the CSV file for reading
with open('static/ciphers.csv', mode='r') as file:
    # Create a CSV reader with DictReader
    csv_reader = csv.DictReader(file)

    # Initialize an empty list to store the dictionaries
    data_list = []

    # Iterate through each row in the CSV file
    for row in csv_reader:
        # Append each row (as a dictionary) to the list
        data_list.append(row)

# Print the list of dictionaries
for data in data_list:
    print(data)