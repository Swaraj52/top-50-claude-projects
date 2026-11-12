# Project Index

All 50 projects in their original order, grouped by the seven original categories.
Generated from `projects.json`; descriptions and features come from the source PDF.

## Contents

- [1. Personal Productivity & Life Management](#1-personal-productivity--life-management) (8 projects)
- [2. Business, Strategy & Operations](#2-business-strategy--operations) (8 projects)
- [3. Marketing, Branding & Content](#3-marketing-branding--content) (8 projects)
- [4. Learning, Research & Knowledge](#4-learning-research--knowledge) (8 projects)
- [5. Finance, Data & Decision Support](#5-finance-data--decision-support) (8 projects)
- [6. Development, Design & Automation](#6-development-design--automation) (6 projects)
- [7. Customer, People & Community](#7-customer-people--community) (4 projects)

## 1. Personal Productivity & Life Management

### 01. Personal Dashboard

- **Folder:** [`PROJECT_01/`](PROJECT_01/)
- **Status:** Completed
- **What it does:** Brings calendar, tasks, reminders, emails and daily priorities together in one clean dashboard.
- **Core features:** Daily briefing, Schedule view, Task tracker, Quick actions
- **Tech stack:** FastAPI · SQLite · React + TypeScript · Claude API
- **Reserved local ports:** backend `8001`, frontend `5101`
- **Notes:** Daybook v1.0: 74 backend + 30 frontend tests; verified end-to-end in a browser incl. a real ICS feed. Claude briefing and IMAP not verified live (no key/credentials).

> Original brief: Calendar, tasks, reminders, emails aur daily priorities ko ek clean dashboard mein laata hai.

### 02. Second Brain / Life Library

- **Folder:** [`PROJECT_02/`](PROJECT_02/)
- **Status:** Completed
- **What it does:** Saves articles, newsletters, YouTube videos and web pages so you can ask questions about them later.
- **Core features:** Content inbox, Tags, Search, Summaries, Ask Your Library
- **Tech stack:** FastAPI · SQLite FTS5 · React + TypeScript · Claude API
- **Reserved local ports:** backend `8002`, frontend `5102`
- **Notes:** Stacks v1.0: 60 backend + 12 frontend tests; live capture of a real Wikipedia article and a real YouTube transcript verified in a browser. Claude summaries/answers not verified live (no key).

> Original brief: Articles, newsletters, YouTube videos aur web pages save karke un par baad mein questions poochne deta hai.

### 03. Daily Review Agent

- **Folder:** [`PROJECT_03/`](PROJECT_03/)
- **Status:** Completed
- **What it does:** At the end of the day, builds a review of completed work, pending tasks and tomorrow's priorities.
- **Core features:** Daily recap, Blockers, Tomorrow plan, Weekly trends
- **Tech stack:** FastAPI · Jinja2 + HTMX · SQLite · Claude API
- **Reserved local ports:** backend `8003`, frontend `5103`
- **Notes:** Shutdown v1.0: 33 backend tests; triage, review and commit verified end-to-end in a browser with the database checked afterwards. Claude review not verified live (no key).

> Original brief: Din ke end par completed work, pending tasks aur kal ki priorities ka review banata hai.

### 04. Personal Goal Tracker

- **Folder:** [`PROJECT_04/`](PROJECT_04/)
- **Status:** Completed
- **What it does:** Breaks long-term goals down into milestones and weekly actions.
- **Core features:** Goal dashboard, Progress tracking, Habit check-ins
- **Tech stack:** FastAPI · Jinja2 + HTMX · SQLite · Claude API
- **Reserved local ports:** backend `8004`, frontend `5104`
- **Notes:** Summit v1.0: 41 backend tests; weighted milestones, pace, weekly actions, check-ins, coach fallback and charts verified in a browser. Claude coach not verified live (no key).

> Original brief: Long-term goals ko milestones aur weekly actions mein todta hai.

### 05. Habit & Routine Coach

- **Folder:** [`PROJECT_05/`](PROJECT_05/)
- **Status:** Pending
- **What it does:** Tracks the user's routines and gives realistic habit suggestions.
- **Core features:** Habit calendar, Streaks, Reflection prompts, Weekly report
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8005`, frontend `5105`

> Original brief: User ke routines ko track karke realistic habit suggestions deta hai.

### 06. Meeting Memory Assistant

- **Folder:** [`PROJECT_06/`](PROJECT_06/)
- **Status:** Pending
- **What it does:** Converts meeting notes into decisions, owners and follow-ups.
- **Core features:** Transcript/notes intake, Action items, Decision log
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8006`, frontend `5106`

> Original brief: Meeting notes ko decisions, owners aur follow-ups mein convert karta hai.

### 07. Email Command Center

- **Folder:** [`PROJECT_07/`](PROJECT_07/)
- **Status:** Pending
- **What it does:** Organizes the inbox into categories and drafts replies and follow-ups.
- **Core features:** Priority inbox, Reply drafts, Follow-up list, Thread summaries
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8007`, frontend `5107`

> Original brief: Inbox ko categories mein organize karke replies aur follow-ups draft karta hai.

### 08. Personal Knowledge Search

- **Folder:** [`PROJECT_08/`](PROJECT_08/)
- **Status:** Pending
- **What it does:** Provides natural-language search across notes, documents and saved resources.
- **Core features:** Semantic search, Source links, Topic clusters
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8008`, frontend `5108`

> Original brief: Notes, documents aur saved resources mein natural-language search provide karta hai.

## 2. Business, Strategy & Operations

### 09. Business Strategy Planner

- **Folder:** [`PROJECT_09/`](PROJECT_09/)
- **Status:** Pending
- **What it does:** Shapes a business idea into a market, positioning, revenue model and execution plan.
- **Core features:** Business canvas, SWOT, Milestones, KPI plan
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8009`, frontend `5109`

> Original brief: Business idea ko market, positioning, revenue model aur execution plan mein shape karta hai.

### 10. Business Operations Hub

- **Folder:** [`PROJECT_10/`](PROJECT_10/)
- **Status:** Pending
- **What it does:** Centralizes recurring business processes, SOPs and team responsibilities.
- **Core features:** SOP library, Process checklist, Ownership tracker
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8010`, frontend `5110`

> Original brief: Recurring business processes, SOPs aur team responsibilities ko centralize karta hai.

### 11. Customer Feedback Analyzer

- **Folder:** [`PROJECT_11/`](PROJECT_11/)
- **Status:** Pending
- **What it does:** Pulls recurring themes and product opportunities out of reviews, surveys and support feedback.
- **Core features:** Sentiment themes, Pain points, Feature requests
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8011`, frontend `5111`

> Original brief: Reviews, surveys aur support feedback se recurring themes aur product opportunities nikalta hai.

### 12. Competitor Research Dashboard

- **Folder:** [`PROJECT_12/`](PROJECT_12/)
- **Status:** Pending
- **What it does:** Compares competitors' positioning, offers, content and differentiators.
- **Core features:** Competitor profiles, Comparison matrix, Opportunity notes
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8012`, frontend `5112`

> Original brief: Competitors ke positioning, offers, content aur differentiators ko compare karta hai.

### 13. Sales Pipeline Assistant

- **Folder:** [`PROJECT_13/`](PROJECT_13/)
- **Status:** Pending
- **What it does:** Helps track leads, deal stages and next actions.
- **Core features:** Lead tracker, Deal summaries, Follow-up drafts
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8013`, frontend `5113`

> Original brief: Leads, deal stages aur next actions ko track karne mein madad karta hai.

### 14. Proposal & Quote Generator

- **Folder:** [`PROJECT_14/`](PROJECT_14/)
- **Status:** Pending
- **What it does:** Drafts a structured proposal, scope, timeline and pricing from a client brief.
- **Core features:** Proposal templates, Scope builder, Revision history
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8014`, frontend `5114`

> Original brief: Client brief se structured proposal, scope, timeline aur pricing draft karta hai.

### 15. SOP Generator

- **Folder:** [`PROJECT_15/`](PROJECT_15/)
- **Status:** Pending
- **What it does:** Turns raw process notes into clear step-by-step standard operating procedures.
- **Core features:** SOP drafts, Role assignments, Checklists
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8015`, frontend `5115`

> Original brief: Raw process notes ko clear step-by-step standard operating procedures mein badalta hai.

### 16. Project Management Command Center

- **Folder:** [`PROJECT_16/`](PROJECT_16/)
- **Status:** Pending
- **What it does:** Keeps projects, deadlines, blockers and team updates in one view.
- **Core features:** Kanban board, Timeline, Risk log, Status reports
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8016`, frontend `5116`

> Original brief: Projects, deadlines, blockers aur team updates ko ek view mein rakhta hai.

## 3. Marketing, Branding & Content

### 17. Brand Kit Generator

- **Folder:** [`PROJECT_17/`](PROJECT_17/)
- **Status:** Pending
- **What it does:** Builds a complete visual identity from a business's voice, audience and values.
- **Core features:** Brand voice, Colors, Fonts, Logo direction, Design rules
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8017`, frontend `5117`

> Original brief: Business voice, audience aur values se complete visual identity banata hai.

### 18. Social Media Content Studio

- **Folder:** [`PROJECT_18/`](PROJECT_18/)
- **Status:** Pending
- **What it does:** Creates platform-wise content ideas, captions and calendars for a brand.
- **Core features:** Content pillars, Post drafts, Calendar, Repurposing
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8018`, frontend `5118`

> Original brief: Brand ke liye platform-wise content ideas, captions aur calendars banata hai.

### 19. Newsletter Studio

- **Folder:** [`PROJECT_19/`](PROJECT_19/)
- **Status:** Pending
- **What it does:** Drafts newsletter editions based on research and brand tone.
- **Core features:** Issue outline, Subject lines, Email layout, Archive
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8019`, frontend `5119`

> Original brief: Research aur brand tone ke basis par newsletter editions draft karta hai.

### 20. Content Repurposing Engine

- **Folder:** [`PROJECT_20/`](PROJECT_20/)
- **Status:** Pending
- **What it does:** Converts one long video, article or podcast into multiple short-form assets.
- **Core features:** Reels scripts, Carousels, Posts, Newsletter snippets
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8020`, frontend `5120`

> Original brief: Ek long video, article ya podcast ko multiple short-form assets mein convert karta hai.

### 21. SEO Content Planner

- **Folder:** [`PROJECT_21/`](PROJECT_21/)
- **Status:** Pending
- **What it does:** Builds a content roadmap based on search intent and topic clusters.
- **Core features:** Keyword groups, Briefs, Internal-link suggestions
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8021`, frontend `5121`

> Original brief: Search intent aur topic clusters ke basis par content roadmap banata hai.

### 22. Campaign Performance Analyst

- **Folder:** [`PROJECT_22/`](PROJECT_22/)
- **Status:** Pending
- **What it does:** Summarizes marketing campaign data and suggests practical next steps.
- **Core features:** Channel metrics, Trend summaries, Experiment ideas
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8022`, frontend `5122`

> Original brief: Marketing campaign data ko summarize karke practical next steps suggest karta hai.

### 23. Landing Page Copy Builder

- **Folder:** [`PROJECT_23/`](PROJECT_23/)
- **Status:** Pending
- **What it does:** Writes conversion-focused landing page copy from the offer, audience and proof points.
- **Core features:** Hero copy, Benefits, FAQs, CTA variations
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8023`, frontend `5123`

> Original brief: Offer, audience aur proof points se conversion-focused landing page copy banata hai.

### 24. Creative Brief Generator

- **Folder:** [`PROJECT_24/`](PROJECT_24/)
- **Status:** Pending
- **What it does:** Turns campaign goals into clear briefs for designers, editors and creators.
- **Core features:** Creative direction, Deliverables, References, Checklist
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8024`, frontend `5124`

> Original brief: Campaign goals ko designers, editors aur creators ke liye clear briefs mein badalta hai.

## 4. Learning, Research & Knowledge

### 25. Research Paper Explainer

- **Folder:** [`PROJECT_25/`](PROJECT_25/)
- **Status:** Pending
- **What it does:** Explains complex research papers in simple language.
- **Core features:** Abstract summary, Methods, Findings, Limitations, Questions
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8025`, frontend `5125`

> Original brief: Complex research papers ko simple language mein explain karta hai.

### 26. YouTube Learning Vault

- **Folder:** [`PROJECT_26/`](PROJECT_26/)
- **Status:** Pending
- **What it does:** Saves educational videos and organizes their transcripts, timestamps and key lessons.
- **Core features:** Video library, Chapter notes, Searchable takeaways
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8026`, frontend `5126`

> Original brief: Educational videos ko save karke transcripts, timestamps aur key lessons organize karta hai.

### 27. Course Companion

- **Folder:** [`PROJECT_27/`](PROJECT_27/)
- **Status:** Pending
- **What it does:** Creates study plans, notes, quizzes and revision sheets from course materials.
- **Core features:** Module tracker, Flashcards, Practice questions
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8027`, frontend `5127`

> Original brief: Course materials se study plans, notes, quizzes aur revision sheets banata hai.

### 28. Personal Tutor

- **Folder:** [`PROJECT_28/`](PROJECT_28/)
- **Status:** Pending
- **What it does:** Teaches a subject step by step at the user's level.
- **Core features:** Adaptive lessons, Examples, Quizzes, Progress checks
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8028`, frontend `5128`

> Original brief: User ke level ke hisaab se kisi subject ko step-by-step sikhata hai.

### 29. Book Notes & Insights Library

- **Folder:** [`PROJECT_29/`](PROJECT_29/)
- **Status:** Pending
- **What it does:** Organizes book highlights and notes into themes and actionable lessons.
- **Core features:** Chapter summaries, Quotes, Topic links, Action list
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8029`, frontend `5129`

> Original brief: Book highlights aur notes ko themes aur actionable lessons mein organize karta hai.

### 30. News Intelligence Briefing

- **Folder:** [`PROJECT_30/`](PROJECT_30/)
- **Status:** Pending
- **What it does:** Summarizes selected news sources by topic into a daily briefing.
- **Core features:** News digest, Source links, Topic trends, Follow-up questions
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8030`, frontend `5130`

> Original brief: Selected news sources ko topic-wise summarize karke daily briefing banata hai.

### 31. Podcast Knowledge Hub

- **Folder:** [`PROJECT_31/`](PROJECT_31/)
- **Status:** Pending
- **What it does:** Stores podcast episodes with transcripts and searchable insights.
- **Core features:** Episode summaries, Quotes, Timestamps, Guest index
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8031`, frontend `5131`

> Original brief: Podcast episodes ko transcripts aur searchable insights ke saath store karta hai.

### 32. Skill Roadmap Builder

- **Folder:** [`PROJECT_32/`](PROJECT_32/)
- **Status:** Pending
- **What it does:** Builds a beginner-to-advanced learning path for a skill.
- **Core features:** Skill map, Weekly plan, Practice projects, Milestones
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8032`, frontend `5132`

> Original brief: Kisi skill ke liye beginner-to-advanced learning path banata hai.

## 5. Finance, Data & Decision Support

### 33. Personal Budget Dashboard

- **Folder:** [`PROJECT_33/`](PROJECT_33/)
- **Status:** Pending
- **What it does:** Organizes income and expenses into categories and shows spending patterns.
- **Core features:** Monthly budget, Category breakdown, Savings goals
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8033`, frontend `5133`

> Original brief: Income aur expenses ko categories mein organize karke spending patterns dikhata hai.

### 34. Subscription Tracker

- **Folder:** [`PROJECT_34/`](PROJECT_34/)
- **Status:** Pending
- **What it does:** Tracks recurring subscriptions, renewal dates and estimated annual costs.
- **Core features:** Subscription list, Renewal alerts, Cost summary
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8034`, frontend `5134`

> Original brief: Recurring subscriptions, renewal dates aur estimated annual costs track karta hai.

### 35. Investment Research Journal

- **Folder:** [`PROJECT_35/`](PROJECT_35/)
- **Status:** Pending
- **What it does:** Keeps investment theses, research notes and a watchlist structured.
- **Core features:** Company notes, Thesis checklist, Risk questions
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8035`, frontend `5135`

> Original brief: Investment thesis, research notes aur watchlist ko structured rakhta hai.

### 36. Expense Insights Analyst

- **Folder:** [`PROJECT_36/`](PROJECT_36/)
- **Status:** Pending
- **What it does:** Finds unusual spending and saving opportunities in expense data.
- **Core features:** Trend analysis, Recurring costs, Monthly comparisons
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8036`, frontend `5136`

> Original brief: Expense data se unusual spending aur saving opportunities identify karta hai.

### 37. Business KPI Dashboard

- **Folder:** [`PROJECT_37/`](PROJECT_37/)
- **Status:** Pending
- **What it does:** Monitors business metrics against goals.
- **Core features:** KPI cards, Trend charts, Weekly commentary
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8037`, frontend `5137`

> Original brief: Business metrics ko goals ke against monitor karta hai.

### 38. Spreadsheet Analyst

- **Folder:** [`PROJECT_38/`](PROJECT_38/)
- **Status:** Pending
- **What it does:** Helps clean, analyze and explain CSV/Excel data.
- **Core features:** Data checks, Pivots, Charts, Insight summary
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8038`, frontend `5138`

> Original brief: CSV/Excel data ko clean, analyze aur explain karne mein help karta hai.

### 39. Decision Journal

- **Folder:** [`PROJECT_39/`](PROJECT_39/)
- **Status:** Pending
- **What it does:** Records the options, assumptions and outcomes of important decisions.
- **Core features:** Decision log, Pros/cons, Confidence, Review dates
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8039`, frontend `5139`

> Original brief: Important decisions ke options, assumptions aur outcomes record karta hai.

### 40. What-If Scenario Planner

- **Folder:** [`PROJECT_40/`](PROJECT_40/)
- **Status:** Pending
- **What it does:** Compares alternative scenarios for business or personal plans.
- **Core features:** Assumptions, Best/base/worst case, Sensitivity notes
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8040`, frontend `5140`

> Original brief: Business ya personal plans ke alternative scenarios compare karta hai.

## 6. Development, Design & Automation

### 41. Website Builder Project

- **Folder:** [`PROJECT_41/`](PROJECT_41/)
- **Status:** Pending
- **What it does:** Turns requirements into a website structure, page copy and implementation plan.
- **Core features:** Sitemap, Wireframe notes, Components, QA checklist
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8041`, frontend `5141`

> Original brief: Requirements se website structure, page copy aur implementation plan banata hai.

### 42. App / MVP Planner

- **Folder:** [`PROJECT_42/`](PROJECT_42/)
- **Status:** Pending
- **What it does:** Converts a product idea into user stories, MVP scope and development tasks.
- **Core features:** PRD, User flows, Feature priorities, Backlog
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8042`, frontend `5142`

> Original brief: Product idea ko user stories, MVP scope aur development tasks mein convert karta hai.

### 43. Codebase Documentation Agent

- **Folder:** [`PROJECT_43/`](PROJECT_43/)
- **Status:** Pending
- **What it does:** Explains an existing codebase and produces documentation and onboarding guides.
- **Core features:** Architecture overview, Setup guide, Module docs
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8043`, frontend `5143`

> Original brief: Existing codebase ko explain karke documentation aur onboarding guides banata hai.

### 44. Code Review Assistant

- **Folder:** [`PROJECT_44/`](PROJECT_44/)
- **Status:** Pending
- **What it does:** Reviews code changes for readability, bugs, security and maintainability.
- **Core features:** Review comments, Risk list, Suggested tests
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8044`, frontend `5144`

> Original brief: Code changes ko readability, bugs, security aur maintainability ke angle se review karta hai.

### 45. QA Test Case Generator

- **Folder:** [`PROJECT_45/`](PROJECT_45/)
- **Status:** Pending
- **What it does:** Drafts manual and automated test cases from requirements and user flows.
- **Core features:** Test scenarios, Edge cases, Regression checklist
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8045`, frontend `5145`

> Original brief: Requirements aur user flows se manual aur automated test cases draft karta hai.

### 46. Automation Workflow Designer

- **Folder:** [`PROJECT_46/`](PROJECT_46/)
- **Status:** Pending
- **What it does:** Maps repeated tasks and suggests automation opportunities and workflows.
- **Core features:** Trigger-action maps, Exception paths, SOPs
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8046`, frontend `5146`

> Original brief: Repeated tasks ko map karke automation opportunities aur workflows suggest karta hai.

## 7. Customer, People & Community

### 47. Customer Support Knowledge Base

- **Folder:** [`PROJECT_47/`](PROJECT_47/)
- **Status:** Pending
- **What it does:** Organizes common customer questions and approved answers into a searchable help center.
- **Core features:** FAQ, Response templates, Escalation rules
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8047`, frontend `5147`

> Original brief: Common customer questions aur approved answers ko searchable help center mein organize karta hai.

### 48. Onboarding Experience Builder

- **Folder:** [`PROJECT_48/`](PROJECT_48/)
- **Status:** Pending
- **What it does:** Builds guided onboarding journeys for new customers or employees.
- **Core features:** Welcome sequence, Checklists, Milestones
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8048`, frontend `5148`

> Original brief: New customers ya employees ke liye guided onboarding journeys banata hai.

### 49. Recruitment Assistant

- **Folder:** [`PROJECT_49/`](PROJECT_49/)
- **Status:** Pending
- **What it does:** Drafts job descriptions, interview questions and evaluation rubrics from role requirements.
- **Core features:** JD, Interview kit, Scorecards, Candidate notes
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8049`, frontend `5149`

> Original brief: Role requirements se job descriptions, interview questions aur evaluation rubrics draft karta hai.

### 50. Team Knowledge Hub

- **Folder:** [`PROJECT_50/`](PROJECT_50/)
- **Status:** Pending
- **What it does:** Keeps team documents, decisions and recurring updates in one central, searchable space.
- **Core features:** Team wiki, Decision records, Meeting summaries
- **Tech stack:** Chosen when the project starts
- **Reserved local ports:** backend `8050`, frontend `5150`

> Original brief: Team documents, decisions aur recurring updates ko central searchable space mein rakhta hai.
