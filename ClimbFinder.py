import json
import os.path
import urllib.request
import parsedatetime as pdt
import re
import time
import smtplib
from time import mktime
from datetime import datetime
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

print("Hello World")

ACTIVITIES_PER_PAGE = 50
BASE_URL = r'https://www.mountaineers.org/explore/activities/@@faceted_query?b_start%5B%5D=0&b_start:int={0}'
CONFIG_FILE = "realConfig.json"

class ActivityRaw:
    def __init__(self, activity_div):
        self.link = activity_div.find(class_="result-title").find("a").get('href')
        title = activity_div.find(class_="result-title").find("a").string
        self.type = title.split('-')[0].strip()
        self.name = title.split('-')[1].strip()
        date = activity_div.find(class_="result-date").string
        self.start_date = date.split('-')[0].strip()
        if(len(date.split('-')) > 1):
            self.end_date = date.split('-')[1].strip()
        else:
            self.end_date = ""
        availability_spans = activity_div.find(class_="result-availability").find_all("span")
        self.participant_availability = " ".join(availability_spans[0].stripped_strings)
        if(len(availability_spans) > 1):
            self.leader_availability = " ".join(availability_spans[1].stripped_strings)
        else:
            self.leader_availability = ""
        self.registration_info = activity_div.find(class_="result-reg").string
        difficulty_div = activity_div.find(class_="result-difficulty")
        if(difficulty_div == None):
            self.difficulty = ""
        else:
            self.difficulty = difficulty_div.string.strip()[12:]
        prereqs_div = activity_div.find(class_="result-prereqs")
        if(prereqs_div == None):
            self.prereqs = ""
        else:
            self.prereqs = prereqs_div.string.strip()[15:]
        branch_div = activity_div.find(class_="result-branch")
        if(branch_div == None):
            self.branch = ""
        else:
            self.branch = branch_div.string.strip()[:-7]

    def to_string(self):
        return "\n".join(
            (self.type,
             self.name,
             self.start_date,
             self.end_date,
             self.participant_availability,
             self.leader_availability,
             self.registration_info,
             self.difficulty,
             self.prereqs,
             self.branch,
             self.link))

class Activity:
    def __init__(self, activity_raw):
        p = pdt.Calendar()
        digits_re = re.compile(r"\d+")
        self.type = activity_raw.type
        self.name = activity_raw.name
        self.start_date = datetime.fromtimestamp(mktime(p.parse(activity_raw.start_date)[0]))
        self.end_date = datetime.fromtimestamp(mktime(p.parse(activity_raw.end_date)[0])) if activity_raw.end_date else None
        self.participant_availability = int(digits_re.match(activity_raw.participant_availability).group(0) if activity_raw.participant_availability else 0)
        self.participant_availability = -1 * self.participant_availability if "waitlist" in activity_raw.participant_availability else self.participant_availability
        self.leader_availability = int(digits_re.match(activity_raw.leader_availability).group(0) if activity_raw.leader_availability else 0)
        self.leader_availability = -1 * self.leader_availability if "waitlist" in activity_raw.leader_availability else self.leader_availability
        self.registration_info = activity_raw.registration_info
        if("opens" in activity_raw.registration_info):
            self.registration_status = "Not yet open"
        elif("closed" in activity_raw.registration_info):
            self.registration_status = "Closed"
        else:
            self.registration_status = "Open"
        self.difficulty = activity_raw.difficulty
        self.prereqs = activity_raw.prereqs
        self.branch = activity_raw.branch
        self.link = activity_raw.link
        self.number_of_days = (self.end_date - self.start_date).days + 1 if self.end_date else 1

    def to_string(self):
        return "\n".join(
            ("Type: -------------- " + self.type,
             "Name:                " + self.name,
             "Start Date: -------- " + self.start_date.strftime("%a, %b %d, %Y"),
             "End Date:            " + (self.end_date.strftime("%a, %b %d, %Y") if self.end_date else ""),
             "Days: -------------- " + str(self.number_of_days),
             "Availability:        " + str(self.participant_availability),
             "Leader Availability: " + str(self.leader_availability),
             "Status:              " + self.registration_status + " (" + self.registration_info + ")",
             "Difficulty: -------- " + self.difficulty,
             "Prereqs:             " + self.prereqs,
             "Branch: ------------ " + self.branch,
             "Link:                " + self.link,
             ))
    
    def to_email_string(self):
        return "\n".join(
            (
             "<div>",
             "<a href={0}>{1}</a>".format(self.link, self.name),
             "<table>",
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Difficulty", self.difficulty),
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Start Date", self.start_date.strftime("%a, %b %d, %y")),
             "<tr><td>{0}</td><td>{1}</td></tr>".format("End Date", (self.end_date.strftime("%a, %b %d, %y") if self.end_date else "")),
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Days", self.number_of_days),
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Availability", str(self.participant_availability) + " open spots"),
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Status", self.registration_status + " (" + self.registration_info + ")"),
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Branch", self.branch),
             "</table>",
             "</div>",
             ))

class RuleFactory:
    def __init__(self):
        self.rules = {}
        
    def register(self, rule):
        self.rules[rule.rule_name] = rule

    def get_rule(self, rule_name):
        return self.rules[rule_name]

class BasicClimbingRule:
    def match(self, activity):
        return activity.type == "Basic Alpine Climb" and activity.participant_availability > 0 and activity.registration_status != "Closed"
		
    rule_name = "BasicClimbingRule"

class EasyKayakingRule:
    def match(self, activity):
        return (
			activity.type == "Sea Kayak" and 
			(
				activity.difficulty == "Sea Kayak I" or 
				activity.difficulty == "Sea Kayak II" or 
				activity.difficulty == "Sea Kayak II+" or 
				activity.difficulty == "Sea Kayak I/II"
			) and 
			activity.participant_availability > 0 and 
			activity.registration_status != "Closed"
                )
		
    rule_name = "EasyKayakingRule"

def getAllActivities():
    activities = []
    page_index = 0
    read_more = True
    while(read_more):
        page = urllib.request.urlopen(BASE_URL.format(str(page_index))).read()
        soup = BeautifulSoup(page)
        activity_divs = soup.find_all(class_="result-item contenttype-mtneers-activity")
        activities.extend([Activity(ActivityRaw(activity_div))for activity_div in activity_divs])
        read_more = len(activity_divs) != 0
        page_index = ACTIVITIES_PER_PAGE + page_index
    return activities

def sendEmail(content, targets, config):
	fromaddr = config["email_username"]
	toaddrs  = ', '.join(targets)
	username = config["email_username"]
	password = config["email_password"]
	msg = MIMEText(content, 'html')
	msg['Subject'] = config["email_subject"]
	msg['From'] = fromaddr
	msg['To'] = toaddrs

	server = smtplib.SMTP('smtp.gmail.com:587')
	server.starttls()
	server.login(username,password)
	print("Sending emails to " + toaddrs)
	server.sendmail(fromaddr, targets, msg.as_string())
	server.quit()

def find_activities(config, rule_factory):
    activities = getAllActivities()

    for rule_group in config["rules"]:
        rule = rule_factory.get_rule(rule_group["rule_name"])
        file_name = rule.rule_name + ".cache"
        if os.path.isfile(file_name):
            infile = open(file_name, 'r')
            seen_links = infile.read().splitlines()
            infile.close()
        else:
            seen_links = []

        print(seen_links)
        filtered_activities = [activity for activity in activities if rule.match(activity)]

        unseen_activities = [activity for activity in filtered_activities if not activity.link in seen_links]

        outfile = open(file_name, 'w')
        for link in [activity.link for activity in filtered_activities]:
            print(link)
            outfile.write("{0}\n".format(link))
        outfile.close()

        print("{0} activities total. {1} met the criteria. {2} have not been seen before".format(len(activities), len(filtered_activities), len(unseen_activities)))
        if(len(unseen_activities) != 0):
            sendEmail(config["email_template"].format("\n<hr \>\n".join([activity.to_email_string() for activity in unseen_activities])), rule_group["distribution_list"], config)

configFile = open(CONFIG_FILE, 'r')
config = json.load(configFile)
rule_factory = RuleFactory()
rule_factory.register(BasicClimbingRule())
rule_factory.register(EasyKayakingRule())
print(config["email_username"])                           
print(config["email_template"])                          
print(config["email_subject"])

while True:
    find_activities(config, rule_factory)
    time.sleep(3600)
