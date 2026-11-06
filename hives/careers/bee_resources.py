"""Curated public starting points, never represented as live openings."""
import re

RESOURCES=[
    {'title':'NSF undergraduate research: student guide','url':'https://www.nsf.gov/funding/initiatives/reu/students','description':'Research directories and application guidance; check each host’s current cycle.','tags':'research lab science internship freshman sophomore'},
    {'title':'NIH Summer Internship Program','url':'https://www.training.nih.gov/research-training/pb/sip/','description':'Official biomedical research program guide; confirm current eligibility and application dates.','tags':'health medical biology biomedical clinical lab research internship'},
    {'title':'MIT resume, cover letter, portfolio and CV resources','url':'https://capd.mit.edu/channels/make-a-resume-cover-letter-cv/','description':'University guidance for preparing application materials.','tags':'resume cv cover letter portfolio writing application'},
    {'title':'CareerOneStop interview preparation','url':'https://www.careeronestop.org/JobSearch/Interview/get-ready.aspx','description':'Interview preparation guidance sponsored by the U.S. Department of Labor.','tags':'interview practice behavior star preparation career job'},
]


def resources_for(question):
    words=set(re.findall(r'[a-z]+',question.casefold()))
    ranked=sorted(RESOURCES,key=lambda item:len(words.intersection(item['tags'].split())),reverse=True)
    selected=[item for item in ranked if words.intersection(item['tags'].split())][:3]
    return [{k:v for k,v in item.items() if k!='tags'} for item in selected]


def local_advice(question):
    q=question.casefold()
    if re.search(r'interview|\bstar\b',q):
        return 'Start with the role’s requirements. Prepare three real examples using Situation, Task, Action, and Result; describe your own contribution and what you learned. Practice a short introduction and two questions for the interviewer. Share the role and one question you want to practice. The resource below is a starting point, not live research.'
    if re.search(r'resume|cover letter|\bcv\b|portfolio',q):
        return 'Choose the role you’re targeting, then connect each important requirement to a real project, course, or work example. Write bullets with an action, what you did, and a supported result. Never invent metrics or experience. Paste a bullet without personal contact details and say which role you want; AI mode can help rewrite it. The resource links are general guidance.'
    if re.search(r'research|\blab\b|professor|cold.email|reach out',q):
        return 'Choose a research area, read a lab’s recent work, and identify one specific connection to your interests. Prepare a short introduction with your relevant coursework, skills, and availability. Ask about undergraduate involvement through the lab’s official contact process. Check host eligibility and current deadlines in the linked directories; these are not verified open positions.'
    if re.search(r'learn|study|skill|career path',q):
        return 'Pick a target role and compare a few real postings for recurring requirements. Choose one skill, build a small project that demonstrates it, and keep a concrete example of what you accomplished. What field are you exploring, and what experience do you already have? Open-ended coaching requires AI mode.'
    return 'I can help explore opportunities, explain concepts, plan learning, prepare interviews, and draft application materials in AI mode. Without an API key, I can provide workBee help, catalog searches, and selected career resources. I can’t reliably answer this open-ended question in local-guide mode. Try a specific career question, or enable Bee AI for broader answers.'
