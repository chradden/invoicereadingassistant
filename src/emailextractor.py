import os
import extract_msg
import pandas as pd
import json
import email
from email import policy
from email.parser import BytesParser

# This object can be used to extract the attachments from emails and also extracts metadata like subject and sender from the email. The medatdata can then be saved as both a csv and json in the data directory.
# TODO: The overwite parameter does not work yet, so the attachments will be saved with a number in the filename if the file already exists.
# The location of the emails is set throught the global email_input_directory variable. The directory, where the attachments are saved is set in the attachments_output_directory variable. Per default they will be in the following directories:

# InvoiceReadingAssistant
#     ├ .venv
#     ├ data
#     │    ├ attachments
#     │    │    └ # the email attachments will be saved here
#     │    ├ emails
#     │    │    └ # the emails you want to extract from go here
#     │    ├ extracted_data.csv
#     │    ├ email_data.csv
#     │    └ email_data.json
#     ├ src
#     │    ├ invoices_LMStudio_Llama3_8B.ipynb
#     │    └ README.md
#     ├ .gitignore
#     ├ README.md
#     └ requirements.txt

class EmailExtractor:
    def __init__(self, input_path, output_dir, mode='directory', overwrite=False, delete=False):
        self.overwrite = overwrite  # overwrite existing attachments files, if they have the same name
        self.delete = delete        # delete emails directly after processing
        self.input_dir = input_path
        self.output_dir = output_dir
        self.email_paths = []
        if mode == 'directory':
            self.email_paths = [os.path.join(input_path, filename) for filename in os.listdir(input_path)]
        elif mode == 'list':
            self.email_paths = input_path

        self.emails = self.process_emails(output_dir)
        self.emails_df = pd.DataFrame.from_dict(self.emails, orient='index')


    def process_emails(self, output_dir):
        # Processes all .msg files in the input directory, extracts email components and attachments and saves the attachments to the specified output directory.
        emails = dict()
        for file_path in self.email_paths:
            filename = os.path.basename(file_path)
            if filename.lower().endswith('.msg'):
                email_data = self.parse_msg_file(file_path, output_dir)
                emails[filename] = email_data
                if self.delete:
                    os.remove(file_path)
                    self.email_paths.remove(file_path)
            elif filename.lower().endswith('.eml'):
                email_data = self.parse_eml_file(file_path, output_dir)
                emails[filename] = email_data
                if self.delete:
                    os.remove(file_path)
                    self.email_paths.remove(file_path)
        return emails

    def parse_msg_file(self, file_path, output_dir):
        # this functions takes a file path to an msg file and output directory as input, extracts email components and attachments and saves the attachments to the specified output directory.
        msg = extract_msg.Message(file_path)
        msg_data = {
            'subject': msg.subject,
            'sender': msg.sender,
            'to': msg.to,
            'cc': msg.cc,
            'bcc': msg.bcc,
            'date': msg.date,
            'body': msg.body,
            'attachments': [att.longFilename for att in msg.attachments if att.longFilename],
            'attachmentpaths': [os.path.join(output_dir, att.longFilename) for att in msg.attachments if att.longFilename]
        }
        print(f"Parsed msg message from: {file_path}")
        self.extract_msg_attachments(msg, output_dir)
        return msg_data

    def extract_msg_attachments(self, msg, output_dir):
        # this function takes a message object and an output directory as input, and saves the attachments to the specified output directory.
        for attachment in msg.attachments:
            filename = self.name_file(output_dir, attachment.longFilename)
            attachment_path = os.path.join(output_dir, filename)
            with open(attachment_path, 'wb') as f:
                f.write(attachment.data)
            print(f"Saved attachment: {attachment_path}")

    def parse_eml_file(self, file_path, output_dir):
        # this functions takes a file path to an msg file and output directory as input, extracts email components and attachments and saves the attachments to the specified output directory.
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            msg = BytesParser(policy=policy.default).parsebytes(raw_data)

        msg_data = {
            'subject': msg['subject'],
            'from': msg['from'],
            'to': msg['to'],
            'cc': msg['cc'],
            'bcc': msg['bcc'],
            'date': msg['date'],
            'body': msg.get_body(preferencelist=('plain', 'html')).get_content() if msg.get_body(preferencelist=('plain', 'html')) else '',
            'attachments': [part.get_filename() for part in msg.iter_attachments() if part.get_filename()],
            'attachmentpaths': [os.path.join(output_dir, part.get_filename()) for part in msg.iter_attachments() if part.get_filename()]
        }
        print(f"Parsed eml message from: {file_path}")
        self.extract_eml_attachments(msg, output_dir)
        return msg_data

    def extract_eml_attachments(self, msg, output_dir):
        # this function takes a message object and an output directory as input, and saves the attachments to the specified output directory.
        for part in msg.iter_attachments():
            if part.get_filename():
                attachment_data = part.get_payload(decode=True)
                filename = self.name_file(output_dir, part.get_filename())
                attachment_path = os.path.join(output_dir, filename)
                with open(attachment_path, 'wb') as f:
                    f.write(attachment_data)
                print(f"Saved attachment: {attachment_path}")

    def name_file(self, filename, output_dir):
        # this function checks, if a filename is already present in the output directory and returns a numbered filename if the file already exists to avoid overwriting.
        if self.overwrite:
            return filename         # overwrite existing attachments files, if they have the same name
        new_filename = filename
        base_name, extension = os.path.splitext(filename)
        count = 1
        while os.path.exists(os.path.join(output_dir, new_filename)):
            new_filename = f'{base_name} ({count}){extension}'
            count += 1
        return new_filename

    def save_as_json(self, file_path, indentation=4):
        # this function saves the extracted email data to a json file.
        with open(file_path, 'w') as f:
            json.dump(self.emails, f, indent=indentation)
        f.close()
        print(f"Saved email data to: {file_path}")

    def save_as_csv(self, file_path, separator=';'):
        # this function saves the extracted email data to a csv file.
        self.emails_df.to_csv(file_path, sep=separator, index=False)
        print(f"Saved email data to: {file_path}")
    
    def delete_emails(self):
        # this function deletes all emails that have been processed.
        for file_path in self.email_paths:
            try:
                os.remove(file_path)
                self.email_paths.remove(file_path)
                print(f"Deleted email: {file_path}")
            except:
                print(f"Error deleting email: {file_path}")


# Example usage
if __name__ == '__main__':
    email_input_directory = '../data/emails'
    if not os.path.exists(email_input_directory):
        os.makedirs(email_input_directory)

    attachments_output_directory = '../data/attachments'
    if not os.path.exists(attachments_output_directory):
        os.makedirs(attachments_output_directory)

    email_data = EmailExtractor(email_input_directory, attachments_output_directory, mode='directory', overwrite=False, delete=False)
    
    email_data_csv_path = '../data/email_data.csv'
    email_data_json_path = '../data/email_data.json'

    email_data.save_as_json(email_data_json_path)
    email_data.save_as_csv(email_data_csv_path)

    email_data.delete_emails()