"""Technical professions across industries; employer sector never makes a role technical."""
import re
from hives.careers.matching import requirements, REQUIREMENTS_VERSION

SECTORS={
 'health_it':'Health IT & digital health','aerospace':'Aerospace & space technology',
 'fintech':'FinTech & financial technology','business_systems':'Business systems & enterprise IT',
 'cybersecurity':'Cybersecurity','cloud_data':'Cloud & data infrastructure',
 'ai_robotics':'AI, robotics & autonomous systems','mobility':'Automotive & mobility technology',
 'biotech':'Bioinformatics & biotechnology','edtech':'Education technology',
 'energy':'Energy, climate & sustainability technology','commerce':'Commerce & logistics technology',
 'defense':'Defense & public-sector technology','hardware':'Hardware & semiconductors',
 'enterprise_software':'Enterprise software & SaaS','consumer':'Consumer & communication technology',
 'other_tech':'Other technical fields',
}
COMPANY_SECTORS={
 'chan zuckerberg initiative':'biotech','lila sciences':'biotech',
 'oscar health':'health_it','commure':'health_it','included health':'health_it','flatiron health':'health_it',
 'spacex':'aerospace','rocket lab':'aerospace','astranis':'aerospace',
 'stripe':'fintech','robinhood':'fintech','sofi':'fintech','ramp':'fintech','brex':'fintech','carta':'fintech',
 'gusto':'business_systems','figma':'enterprise_software','notion':'enterprise_software','klaviyo':'commerce','toast':'commerce','flexport':'commerce',
 'cloudflare':'cloud_data','databricks':'cloud_data','mongodb':'cloud_data',
 'duolingo':'edtech','zoox':'mobility','palantir':'defense','anthropic':'ai_robotics',
 'ai2 allen institute for ai':'ai_robotics','recursion':'biotech','reddit':'consumer','discord':'consumer',
}
NON_TECH=re.compile(r'\b(?:recruiter|recruiting|account executive|sales representative|business development|registered nurse|nurse practitioner|physician assistant|therapist|pharmacist|medical assistant|care coordinator|care manager|care navigator|payroll specialist|accountant|legal counsel|lawyer|social worker|teacher|hotel|restaurant|data entry)\b',re.I)
TECH_TITLE=re.compile(r'\b(?:lab|laboratory|instrumentation) (?:technician|engineer|automation|scientist)\b|\b(?:engineer(?:ing)?|software|developer|programmer|devops|sre|informatics|bioinformatics|computational|robotics|avionics|firmware|cybersecurity|appsec|scientist)\b|\b(?:data|systems?|network|security|database|cloud|infrastructure|solutions?|integration|enterprise|technical|IT) (?:architect|analyst|administrator|specialist|consultant|technician|support|developer|engineer|manager)\b|\b(?:UX|UI|product designer|technical product manager|technical program manager|technical project manager|business systems|business intelligence|information technology|information systems|IT support|HRIS|EHR|EMR)\b',re.I)
TECH_SKILLS={'Python','Java','JavaScript','TypeScript','SQL','PostgreSQL','React','Node.js','C++','C#','Go','Rust','Docker','Kubernetes','AWS','Linux','TensorFlow','PyTorch','Swift','Tableau','Power BI','Pandas','NumPy','Scikit-learn','FastAPI','Django','Flask','HTML','CSS','GitHub','R','SPSS','Stata','SAS','Snowflake','Databricks','dbt','MongoDB','Redis','Azure','Google Cloud','AutoCAD','SolidWorks','MATLAB','LabVIEW','Circuit design'}


def technical_role(job):
    title=job['title']
    if NON_TECH.search(title): return False,'Non-technical professional title'
    found=TECH_TITLE.search(title)
    if found:return True,'Technical role signal in title: '+found.group(0)
    if re.search(r'\b(?:analyst|specialist|consultant|research|intern|co-op)\b',title,re.I):
        rows=job.get('requirements') if job.get('requirements_version')==REQUIREMENTS_VERSION else requirements(job.get('description',''))
        supported=sorted({s for r in rows or [] if r['kind'] in {'required','preferred'} for s in r['skills'] if s in TECH_SKILLS})
        if supported:return True,'Technical tools in posting requirements: '+', '.join(supported[:5])
    return False,'No explicit technical role or tool requirement recognized'


def sector_tags(job):
    title=job['title'];company=re.sub(r'[^a-z0-9]+',' ',job['company'].casefold()).strip()
    result=[]
    known=COMPANY_SECTORS.get(company)
    if known:result.append(known)
    for key,pattern in [
      ('health_it',r'informatics|EHR|EMR|digital health|health IT|medical software|clinical systems'),
      ('aerospace',r'aerospace|avionics|satellite|spacecraft|propulsion|flight software|flight controls'),
      ('business_systems',r'business systems|business intelligence|enterprise applications|ERP|HRIS|salesforce|SAP'),
      ('cybersecurity',r'cybersecurity|security engineer|security analyst|information security|appsec|security architect'),
      ('cloud_data',r'cloud|data engineer|database|infrastructure|devops|SRE'),
      ('ai_robotics',r'machine learning|\bAI\b|robotic|autonom'),
      ('biotech',r'bioinformatics|computational biolog|laboratory automation|biomedical'),
      ('energy',r'energy|climate|renewable|solar|wind turbine|sustainab|battery'),
      ('hardware',r'hardware|semiconductor|electrical|electronics|embedded|circuit|FPGA'),
      ('mobility',r'automotive|vehicle|self-driving'),
      ('edtech',r'education technology|learning platform|educational software'),
      ('commerce',r'commerce|logistics|supply chain systems|warehouse automation'),
      ('defense',r'defense|defence|national security|public sector')]:
        if re.search(pattern,title,re.I) and key not in result:result.append(key)
    return result or ['other_tech']
