# insecure-ai-agents
Examples of purposely insecure code for AI Agents

## I created an AI Agent project that finds available ALS clinical trials and recommends patients for each trial.

## create_patient_db.py 
Creates a SQLite db with fake patient data with the following columns

- name
- age
- gender
- diagnosis_date
- alsfrs_r_score  (Scores disease progression. It ranges from 0 (severe disability) to 48 (normal function))
- fvc_percentage (Forced Vital Capacity percentage, showing varying lung capacities.)
- is_bulbar_onset (Indicates if the ALS onset is bulbar (1) or limb (0))


## get_patients_fit_for_als_trials.py 
Creates two worker agents supervised by another. One worker agent has access to the patient database and another has access to the internet and performs web-scrapping to get current available trial data from Johns Hopkins website. The prompt to the multiagent system is `"Find ALS clinical trials, then recommend patients in the database for each trial"`. The agents then work together to come up with a list of patients likely to be a fit for each trial. The agents are prompted to only recommend a candidate for trial if they are likely to outlive the Length of Study for each trial, based on their alsfrs_r and fvc_percentage scores.


## LangSmith Capture of a Successful Run
https://smith.langchain.com/public/c132eb00-22f3-436c-87a1-3b8feca03a60/r


## Call for Code Review
Code review welcome from AI engineers that work with these frameworks more often than I do!


## Security Review Coming Soon!
An in depth security review of this code is coming. I wrote this for fun and to use it as a way to showcase certain security concerns for AI Agents. I plan to submit it to OWASP as an insecure code sample which will be used to create security guidance on AI Agents.
