import json
import os.path
import urllib.request
import re
import time
import smtplib
from time import mktime
from datetime import datetime
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from dateutil.parser import parse

print("Hello World")

ACTIVITIES_PER_PAGE = 50
BASE_URL = r'https://www.mountaineers.org/explore/activities/@@faceted_query?b_start%5B%5D=0&b_start:int={0}'
PUBLIC_CONFIG_FILE = "publicConfig.json"
PRIVATE_CONFIG_FILE = "privateConfig.json"

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
        registration_info_div = activity_div.find(class_="result-reg")
        if(registration_info_div == None):
            self.registration_info = ""
        else:
            self.registration_info = registration_info_div.string
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
        digits_re = re.compile(r"\d+")
        self.type = activity_raw.type
        self.name = activity_raw.name
        self.start_date = parse(activity_raw.start_date)
        self.end_date = parse(activity_raw.end_date) if activity_raw.end_date else None
        self.participant_availability = int(digits_re.match(activity_raw.participant_availability).group(0) if activity_raw.participant_availability else 0)
        self.participant_availability = -1 * self.participant_availability if "waitlist" in activity_raw.participant_availability else self.participant_availability
        self.leader_availability = int(digits_re.match(activity_raw.leader_availability).group(0) if activity_raw.leader_availability else 0)
        self.leader_availability = -1 * self.leader_availability if "waitlist" in activity_raw.leader_availability else self.leader_availability
        self.registration_info = activity_raw.registration_info if activity_raw.registration_info else None
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
        status = self.registration_status
        if(self.registration_info):
            status = status + " (" + self.registration_info + ")"
        return "\n".join(
            ("Type: -------------- " + self.type,
             "Name:                " + self.name,
             "Start Date: -------- " + self.start_date.strftime("%a, %b %d, %Y"),
             "End Date:            " + (self.end_date.strftime("%a, %b %d, %Y") if self.end_date else ""),
             "Days: -------------- " + str(self.number_of_days),
             "Availability:        " + str(self.participant_availability),
             "Leader Availability: " + str(self.leader_availability),
             "Status:              " + status,
             "Difficulty: -------- " + self.difficulty,
             "Prereqs:             " + self.prereqs,
             "Branch: ------------ " + self.branch,
             "Link:                " + self.link,
             ))
    
    def to_email_string(self):
        status = self.registration_status
        if(self.registration_info):
            status = status + " (" + self.registration_info + ")"
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
             "<tr><td>{0}</td><td>{1}</td></tr>".format("Status", status),
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
        return (activity.type == "Basic Alpine Climb" or activity.type == "Glacier Climb") and activity.participant_availability > 0 and activity.registration_status != "Closed"
		
    rule_name = "Basic Climb"

class GlacierClimbingRule:
    def match(self, activity):
        return (activity.type == "Glacier Climb") and activity.participant_availability > 0 and activity.registration_status != "Closed"
		
    rule_name = "Glacier Climb"

class BasicClimbingLeaderRule:
    def match(self, activity):
        return (activity.type == "Basic Alpine Climb" or activity.type == "Glacier Climb") and activity.leader_availability > 0 and activity.registration_status != "Closed"
		
    rule_name = "Basic Climb Leader"

class IntermediateClimbingRule:
    def match(self, activity):
        return (activity.type == "Intermediate Alpine Climb") and activity.participant_availability > 0 and activity.registration_status != "Closed"
		
    rule_name = "Intermediate Climb"

class ScramblingRule:
    def match(self, activity):
        return (activity.type == "Alpine Scramble") and activity.participant_availability > 0 and activity.registration_status != "Closed"
		
    rule_name = "Alpine Scramble"

class KayakingRule:
    def match(self, activity):
        return (
			activity.type == "Sea Kayak"  and 
			activity.participant_availability > 0 and 
			activity.registration_status != "Closed"
                )
		
    rule_name = "Kayaking"

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

def sendEmail(content, subject, targets, privateConfig):
	fromaddr = privateConfig["email_username"]
	toaddrs  = ', '.join(targets)
	username = privateConfig["email_username"]
	password = privateConfig["email_password"]
	msg = MIMEText(content, 'html')
	msg['Subject'] = subject
	msg['From'] = fromaddr
	msg['To'] = toaddrs

	server = smtplib.SMTP('smtp.gmail.com:587')
	server.starttls()
	server.login(username,password)
	print("Sending emails to " + toaddrs)
	server.sendmail(fromaddr, targets, msg.as_string())
	server.quit()

def execute(publicConfig, privateConfig, rule_factory):
    activities = getAllActivities()
    rule_to_activities = build_rule_to_activities(activities, [rule["rule_name"] for rule in publicConfig["rules"]])
    for name, rules in name_to_rules.items():
        has_content = False
        email_body = ""
        for rule in rules:
            if(len(rule_to_activities[rule["rule_name"]]) != 0):
                has_content = True
                email_body = email_body + "<h1>" + rule["rule_name"] + "</h1>" + "\n<hr \>\n".join([activity.to_email_string() for activity in rule_to_activities[rule["rule_name"]]])

        if(has_content):
            print("sending email to {0}".format(name))
            sendEmail(publicConfig["email_template"].format(email_body, name), publicConfig["email_subject"], [name + "@googlegroups.com"], privateConfig)

def build_rule_to_activities(activities, rule_names):
    rule_to_activites = {}
    for rule_name in rule_names:
        rule = rule_factory.get_rule(rule_name)
        seen_links = get_seen_links(rule_name)

        filtered_activities = [activity for activity in activities if rule.match(activity)]
        set_seen_links(rule.rule_name, filtered_activities)

        unseen_activities = [activity for activity in filtered_activities if not activity.link in seen_links]
        rule_to_activites[rule_name] = unseen_activities
        print("For {3}: {0} activities total. {1} met the criteria. {2} have not been seen before".format(len(activities), len(filtered_activities), len(unseen_activities), rule_name))
    return rule_to_activites


def get_seen_links(rule_name):
    file_name = rule_name + ".cache"
    seen_links = []
    if os.path.isfile(file_name):
        infile = open(file_name, 'r')
        seen_links = infile.read().splitlines()
        infile.close()
    return seen_links

def set_seen_links(rule_name, filtered_activities):
    file_name = rule_name + ".cache"
    outfile = open(file_name, 'w')
    for link in [activity.link for activity in filtered_activities]:
        outfile.write("{0}\n".format(link))
    outfile.close()
        

publicConfigFile = open(PUBLIC_CONFIG_FILE, 'r')
publicConfig = json.load(publicConfigFile)
privateConfigFile = open(PRIVATE_CONFIG_FILE, 'r')
privateConfig = json.load(privateConfigFile)
name_to_rules = {}
for rule_group in publicConfig["rules"]:
    for email in rule_group["distribution_lists"]:
        if not email in name_to_rules:
            name_to_rules[email] = []
        name_to_rules[email].append(rule_group)

rule_factory = RuleFactory()
rule_factory.register(BasicClimbingRule())
rule_factory.register(BasicClimbingLeaderRule())
rule_factory.register(IntermediateClimbingRule())
rule_factory.register(ScramblingRule())
rule_factory.register(KayakingRule())
rule_factory.register(GlacierClimbingRule())
print(privateConfig["email_username"])                           
print(publicConfig["email_template"])                          
print(publicConfig["email_subject"])

while True:
    execute(publicConfig, privateConfig, rule_factory)
    time.sleep(3600)
