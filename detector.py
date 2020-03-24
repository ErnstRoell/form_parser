import requests
import time
import os
import json
from PIL import Image
from io import BytesIO
import datetime
import pprint as pp
import pandas as pd
from PyPDF2 import PdfFileWriter, PdfFileReader
import datetime
import pprint as PyPDF2
import sys
import glob

def get_base_name(filename):
    base = os.path.basename(filename)
    return os.path.splitext(base)[0]


class detector():
    def __init__(self):
        # Add your Computer Vision subscription key and endpoint to your environment variables.
        if 'COMPUTER_VISION_SUBSCRIPTION_KEY' in os.environ:
            self.subscription_key = os.environ['COMPUTER_VISION_SUBSCRIPTION_KEY']
        else:
            print("\nSet the COMPUTER_VISION_SUBSCRIPTION_KEY environment variable.\n**Restart your shell or IDE for changes to take effect.**")
            sys.exit()

        if 'COMPUTER_VISION_ENDPOINT' in os.environ:
            self.endpoint = os.environ['COMPUTER_VISION_ENDPOINT']
        else:
            print("\nSet the COMPUTER_VISION_SUBSCRIPTION_KEY environment variable.\n**Restart your shell or IDE for changes to take effect.**")
            sys.exit()

        self.analyze_url = self.endpoint + "vision/v2.1/read/core/asyncBatchAnalyze"
        self.filenames = []
        self.filenames_analysis = []
        self.regionOfInterest = {"factuurnummer":{"lowerLeft":(20, 600),
                                    "upperRight":(200, 630)},
                                "adres":{"lowerLeft":(10, 670),
                                    "upperRight":(400, 800)}}
        self.files = {}

    def load_pdf(self,file):
        with open(file, "rb") as in_f:
            input1 = PdfFileReader(in_f)
            numPages = input1.getNumPages()

            for i in range(numPages):
                output = PdfFileWriter()
                page = input1.getPage(i)
#                 print(page.mediaBox)

                # Generate file id
                file_id = id(datetime.datetime.now())
                output.addPage(page)
                filename = "./parsed/{}_{}.pdf".format(get_base_name(file),file_id) # Test if indeed correct!

                # Add file path to the JSON of the det
                self.files[file_id] = {'filepath':filename}
                with open(filename, "wb") as out_f:
                    output.write(out_f)


    def load_roi(self,file):
        """
        Set's up the structure self.file as if the pdf was loaded.
        """
        file_id = id(datetime.datetime.now())
        filename = "./parsed/{}_{}.pdf".format(get_base_name(file),file_id) # Test if indeed correct!

        # Add file path to the JSON of the det
        self.files[file_id] = {'filepath':filename}

    
    def crop_page(self, pdf_file=None):
        if pdf_file is not None:
            self.files={}
            self.load_pdf(pdf_file)

        for file_id in self.files.keys():
            pdf_file = self.files[file_id]['filepath']
            with open(pdf_file, "rb") as in_f:
                page = PdfFileReader(in_f).getPage(0)
                #numPages = page.getNumPages()
                #if numPages > 1:
                #    print("ERROR")
                #page = self.load_page(self.files[file_id]['filepath'])
                for key in self.regionOfInterest.keys():
                    page.trimBox.lowerLeft = self.regionOfInterest[key]['lowerLeft']
                    page.trimBox.upperRight = self.regionOfInterest[key]['upperRight']
                    page.cropBox.lowerLeft = self.regionOfInterest[key]['lowerLeft']
                    page.cropBox.upperRight = self.regionOfInterest[key]['upperRight']
                    filename = "./roi/{}_{}.pdf".format(get_base_name(self.files[file_id]['filepath']),key) # Test if indeed correct!
                    output = PdfFileWriter()
                    output.addPage(page)
                    with open(filename, "wb") as out_f:
                        output.write(out_f)
                    
                    # Add the info to the json files
                    # First path to the cropped file
                    self.files[file_id][key + "_path"] = filename 

    def pdf2text(self, pdf_file=None):
        '''
        Takes an pdf path in and spits the extracted text out.
               
        '''

        headers = {'Ocp-Apim-Subscription-Key': self.subscription_key,
                   'Content-Type': 'application/octet-stream'}

        params = {'visualFeatures': 'Categories,Description,Color'}

        image_data = open(pdf_file, "rb").read()
        response = requests.post(
                self.analyze_url, 
                headers=headers, 
                params=params, 
                data=image_data)

        response.raise_for_status()

        # Extracting text requires two API calls: One call to submit the
        # Image for processing, the other to retrieve the text found in the image.
        # The recognized text isn't immediately available, so poll to wait for completion.
        analysis = {}
        poll = True
        while (poll):
            response_final = requests.get(
                response.headers["Operation-Location"], headers=headers)
            analysis = response_final.json()
        #     print(analysis)
            time.sleep(1)
            if ("recognitionResults" in analysis):
                poll = False
            if ("status" in analysis and analysis['status'] == 'Failed'):
                poll = False
        return analysis

    def convert_files(self, pdf_file=None):
        if pdf_file is not None:
            self.files={}
            self.load_pdf(pdf_file)
            self.crop_page()
        
        # Apply the conversion on each element in the files list and on each roi
        for id in self.files.keys():
            for roi_key in self.regionOfInterest.keys():
                # Send the text to the Cognitive services
#                # Below is a mock response
#                with open(r"C:\Users\erroell\Documents\form\test\testanalysis.json",'r') as f:
#                    #result = {"text":"This is text for file id {} and roi {}".format(id,roi_key)}
#                    result = json.load(f)
                pdf_file = self.files[id][roi_key +'_path']
                result = self.pdf2text(pdf_file)

                filename="./analysis/{}_analysis.json".format(get_base_name(self.files[id][roi_key +'_path']))
                
                # Add the info to the json files
                # First path to the cropped file
                try:
                    self.files[id][roi_key + "_analysis"].append(filename)
                except KeyError:
                    self.files[id][roi_key + "_analysis"] = filename 
              
                with open(filename,"w") as f:
                    json.dump(result,f,indent=4)

    def parse_json(self,filename):
        with open(filename,'r') as f:
            data = json.load(f)

        text = []
        try:
            if data['status'] =='Succeeded':
                for line in data['recognitionResults'][0]['lines']:
                    text.append(line['text'])
        except KeyError:
            text = []
        return text

    def parse_analysis(self):
        for id in self.files.keys():
            for roi_key in self.regionOfInterest.keys():
                text = self.parse_json(self.files[id][roi_key + "_analysis"])
                try:
                    self.files[id][roi_key + "_result"].append(text)
                except KeyError:
                    self.files[id][roi_key + "_result"] = text 


if __name__ == "__main__":
    pdf_path = "./data/example.pdf"

    files = glob.glob('./roi/*')
    for f in files:
        os.remove(f)

    det = detector()
    det.load_pdf(pdf_path)
    det.crop_page()
    det.convert_files()
    det.parse_analysis()
    pp.pprint(det.files)

    with open("result.json",'w') as f:
        json.dump(det.files,f,indent=4)

