# TRACECLAUSE AI (SCANSHIELD AI V2) PRIVACY POLICY

**Effective Date:** September 4, 2026  
**Last Updated:** September 4, 2026  

---

### OUR COMMITMENT TO YOUR PRIVACY & DATA PROTECTION

At **TraceClause AI** (operated under ScanShield AI v2, hereinafter referred to as "**TraceClause AI**", "**Company**", "**we**", "**us**", or "**our**"), we understand that legal contracts and agreement documents contain highly sensitive, proprietary, and confidential business information. We are committed to maintaining enterprise-grade standards of data privacy, confidentiality, and security across our website, application programming interfaces (APIs), software applications, web dashboard hosted at `https://traceclause.vercel.app`, and contract auditing services (collectively, the "**Services**").

This Privacy Policy explains how we collect, use, process, disclose, transfer, and protect your Personal Data and Document Data when you access or use our Services, and outlines your rights under global privacy frameworks, including the **General Data Protection Regulation (GDPR)** (EU/UK), the **California Consumer Privacy Act as amended by the California Privacy Rights Act (CCPA/CPRA)**, and the **Digital Personal Data Protection Act, 2023 (DPDPA)** (India).

---

## 1. INFORMATION WE COLLECT

We collect information directly from you, automatically through your interaction with our platform, and through processing legal documents you submit. We categorize the data we collect as follows:

### 1.1 User-Provided Account & Billing Data
When you register an account, subscribe to a plan, or communicate with us, we collect:
- **Account Credentials:** Full name, business email address, company name, job title, encrypted password hash, and profile details;
- **Billing & Subscription Details:** Subscription tier selection (Free Trial, Solo Plan, or Team Plan), billing currency (USD or INR), invoice history, tax identifiers (e.g., GSTIN or VAT numbers), and transaction metadata.  
  *Note:* All payment processing is handled authoritatively and directly by our PCI-DSS Level 1 compliant payment processor (**Razorpay Software Private Limited**). TraceClause AI does not collect or store raw payment card numbers, CVVs, or bank account credentials on its servers;
- **Support & Communications:** Correspondence, support tickets, and feedback submitted to our team.

### 1.2 Automatically Collected Data & System Telemetry
When you navigate our web application or execute API calls, we automatically log technical diagnostic data:
- **Device & Connection Data:** IP address, browser type and version, user agent header, operating system, time zone setting, and preferred language;
- **Usage & Interaction Logs:** Feature usage metrics, endpoint API requests, timestamp of contract uploads, analysis latency, error logs, and token utilization telemetry;
- **Cookies & Storage Technologies:** Session cookies and local storage items necessary to maintain user authentication states, workspace context, and application preferences.

### 1.3 AI Input Data, Contracts & Vector Embeddings
To perform legal contract audits and interactive RAG Q&A, we collect and process:
- **Uploaded Document Content:** PDF files, Microsoft Word (`.docx`) documents, raw agreement text, and custom audit prompt instructions ("**User Content**" or "**Prompts**");
- **Extracted Text & Metadata:** Document line numbers, extracted clause text, defined terms, and structural contract headings;
- **Vector Embeddings:** 1536-dimensional high-precision vector representations generated via Matryoshka Representation Learning (MRL) embeddings (`text-embedding-3-small` / `gemini-embedding-001`) stored securely in our Supabase `pgvector` database to enable citation-linked Retrieval-Augmented Generation (RAG).

---

## 2. HOW WE USE INFORMATION & ZERO AI TRAINING POLICY

### 2.1 Core Application Delivery & Contract Auditing
We process your data strictly to deliver, execute, and maintain the Services, specifically to:
- Parse uploaded legal contracts and extract structural text;
- Perform multi-LLM risk analysis, clause evaluation, and counter-language generation;
- Stream interactive citation-linked RAG responses during contract Q&A chat sessions;
- Generate downloadable Microsoft Word (`.docx`) redline reports featuring track-changes visual formatting;
- Provision and manage multi-seat workspace permissions and workspace-aware Row Level Security (RLS) policies.

### 2.2 Analytics, Platform Security & Operations
We utilize operational system telemetry to:
- Monitor server performance, backend FastAPI middleware health, and API response rates;
- Detect, prevent, and mitigate unauthorized API scraping, rate limit evasion, and security breaches;
- Manage subscription quotas (e.g., enforcing 3 free trial audits, 20 Solo plan reviews, or 100 Team plan pooled reviews).
*Note:* System logs may contain pseudonymous operational identifiers (such as user UUIDs, uploaded contract filenames, timestamp, and token counts) necessary for quota integrity and audit logging. Our application logs strictly exclude contract text, prompt payloads, model outputs, and payment credentials.

### 2.3 ARTIFICIAL INTELLIGENCE SUB-PROCESSING & DATA HANDLING
We utilize commercial enterprise API endpoints provided by our AI partners (Anthropic PBC, OpenAI LLC, and Google LLC). 
- **Processing Scope:** Contract text excerpts and prompt instructions are transmitted via encrypted TLS directly to AI sub-processor endpoints for real-time risk assessment, clause evaluation, and vector embedding generation.
- **Provider Terms:** Data processing and retention by these third-party providers are governed by their respective standard commercial API data processing agreements.
- **Zero Application Logging:** TraceClause AI application services strictly minimize logging and do not write contract clause text, prompts, model responses, access tokens, or payment details to application log files.

---

## 3. DATA SHARING & THIRD-PARTY SUB-PROCESSORS

We do not sell, rent, trade, or monetize your Personal Data or Document Data to third parties. We share your data only with trusted third-party sub-processors necessary to operate our infrastructure, as detailed below:

| Processor Category | Vendor / Entity | Purpose & Function | Data Transferred | Location |
| :--- | :--- | :--- | :--- | :--- |
| **LLM & AI Processing** | **Anthropic PBC** | Claude 3.5 Sonnet API reasoning & counter-language generation | Contract text snippets, prompts | United States |
| **LLM & AI Processing** | **OpenAI LLC** | GPT-4o API reasoning & `text-embedding-3-small` vectorization | Contract text snippets, prompts | United States |
| **LLM & AI Processing** | **Google LLC** | Gemini 1.5 Pro & `gemini-embedding-001` (1536-dim MRL embeddings) | Contract text snippets, prompts | United States |
| **Vector DB & Auth** | **Supabase Inc.** | PostgreSQL database, `pgvector` storage, Auth & RLS policies | User accounts, metadata, vector embeddings | United States / EU |
| **Frontend Infrastructure** | **Vercel Inc.** | Web application edge hosting, static asset delivery, CDN | Web traffic telemetry, IP addresses | Global / United States |
| **Payment Processor** | **Razorpay Software Pvt. Ltd.** | Hosted checkout & domestic/international billing (Cards, UPI, Netbanking) | Customer name, email, plan tier, notes | India |

### 3.4 Legal Disclosures & Law Enforcement
We may disclose your information if required to do so by applicable law, court order, search warrant, subpoena, or governmental regulation, or if we believe in good faith that such disclosure is necessary to protect the rights, property, or safety of TraceClause AI, our users, or the general public.

---

## 4. INTERNATIONAL DATA TRANSFERS

Because TraceClause AI operates globally, your information may be transferred to, stored, and processed in countries outside of your state, province, or nation of residence—including the **Republic of India** and the **United States**—where data protection laws may differ from those in your jurisdiction.

### 4.1 Cross-Border Safeguards & Transfer Mechanisms
When transferring Personal Data originating from the European Economic Area (EEA), United Kingdom (UK), or Switzerland to third countries, we ensure appropriate safeguards are implemented:
- **Standard Contractual Clauses (SCCs):** We rely upon the European Commission's approved Standard Contractual Clauses (and the UK International Data Transfer Addendum) with our cloud hosting and AI sub-processors;
- **EU-U.S. Data Privacy Framework (DPF):** Our United States sub-processors (including Google, OpenAI, Anthropic, and Vercel) maintain active certifications under the EU-U.S. Data Privacy Framework and its UK Extension;
- **Indian DPDPA Safeguards:** For users in India, cross-border transfers are conducted in compliance with notified regulations of the Central Government under Section 16 of the Digital Personal Data Protection Act, 2023.

---

## 5. DATA RETENTION & DELETION

### 5.1 Account & Transaction Data Retention
We retain your account registration data (name, email, subscription status) for as long as your account remains active. If you cancel your subscription or close your account, we retain minimal transaction records for up to seven (7) years to comply with statutory tax, auditing, and financial accounting laws.

### 5.2 Document & Vector Embedding Retention
- **Transient In-Memory Processing:** Raw uploaded files (PDF/DOCX) sent to `/api/v1/documents/upload` are parsed strictly in server memory (RAM) via byte streams without being stored on server disk. Concurrency is throttled to 3 simultaneous in-memory extractions per worker to prevent resource exhaustion. Legacy binary `.doc` files are not supported.
- **Temporary Payload Staging:** In asynchronous background queue analysis flows, extracted text is temporarily staged in `staged_job_payloads` exclusively while the analysis worker processes the job. Upon reaching a terminal state (`completed` or `failed`), the staged raw text is permanently and automatically deleted immediately.
- **User-Controlled Database Storage:** To power the Audit Vault, DOCX redline export, and citation-linked RAG chat, extracted clause text snippets, risk analyses, counter-language recommendations, and 1536-dimensional vector embeddings are stored in your isolated database record for as long as you maintain the audit in your account.
- **Immediate Deletion Controls:** Users have full control over retained contract content:
  - **Individual Report Deletion:** You can permanently delete any individual report, its clause text, and associated vector embeddings at any time directly from the Audit Vault dashboard or via `DELETE /api/v1/contract/{report_id}`.
  - **Account-Level Purge:** You can permanently delete your entire account and all associated contract reports, embeddings, and quota logs via `DELETE /api/v1/contract/delete-account`.
  - **Ephemeral Analysis Mode:** You can opt to execute audits with `retain_audit: false`, which returns the audit results without persisting clause texts or embeddings to the database.
- **Database Backup Roll-Off:** When a contract report or user account is deleted, it is deleted immediately from primary operational databases. Any residual records present in encrypted point-in-time database backups expire and roll off within the cloud provider's standard 30-day backup retention cycle without being restored to production.

---

## 6. YOUR GLOBAL PRIVACY RIGHTS

Depending on your geographical location, you possess specific legal rights regarding your Personal Data:

### 6.1 European Union & United Kingdom Rights (GDPR / UK GDPR)
If you reside in the EEA or UK, you have the right to:
- **Right of Access:** Request a copy of the Personal Data we hold about you;
- **Right to Rectification:** Request correction of inaccurate or incomplete Personal Data;
- **Right to Erasure ("Right to be Forgotten"):** Request permanent deletion of your Personal Data;
- **Right to Restrict Processing:** Request that we temporarily or permanently restrict processing of your data;
- **Right to Data Portability:** Obtain your Personal Data in a structured, commonly used, machine-readable format;
- **Right to Object:** Object to processing based on legitimate interests or direct marketing.

### 6.2 California Resident Rights (CCPA / CPRA)
If you are a resident of California, you possess the following rights:
- **Right to Know / Access:** Request disclosure of categories and specific pieces of Personal Data collected, sources, and third parties shared with;
- **Right to Delete:** Request deletion of Personal Data collected from you;
- **Right to Correct:** Request correction of inaccurate Personal Data;
- **Right to Opt-Out of Sale or Sharing:** **TraceClause AI does NOT sell your Personal Data or share it for cross-context behavioral advertising.** Therefore, we do not offer an opt-out link;
- **Right to Non-Discrimination:** We will not discriminate against you for exercising any of your CPRA rights.

### 6.3 Indian Resident Rights (DPDPA 2023)
If you reside in India, under the Digital Personal Data Protection Act, 2023, you have the right to:
- Request summary of personal data processed and processing activities;
- Request correction, completion, and updating of personal data;
- Withdraw consent for processing at any time;
- Access readily available grievance redressal mechanisms;
- Nominate another individual to exercise your rights in the event of death or incapacity.

---

## 7. SECURITY & PROTECTION MEASURES

We implement robust, market-standard technical and organizational security measures to protect your data against unauthorized access, loss, alteration, or destruction:
- **Encryption in Transit:** All traffic between your browser, Vercel frontend, and FastAPI backend is encrypted using TLS 1.3 / SSL protocols;
- **Encryption at Rest:** Vector embeddings and database tables in Supabase are encrypted at rest using AES-256 encryption;
- **Access Controls & RLS:** Multi-seat workspace access is strictly isolated using Supabase Row Level Security (RLS) policies and FastAPI feature-gating authorization middleware (`require_feature`).

---

## 8. CONTACT INFORMATION & GRIEVANCE OFFICER

If you wish to exercise any of your privacy rights, submit a data protection inquiry, or file a complaint regarding our data practices, please contact our dedicated Privacy Compliance Team:

**TraceClause AI Privacy & Compliance Department**  
**Data Protection Officer (DPO) / Grievance Officer**  
**Email:** `privacy@traceclause.ai`  
**General Support:** `support@traceclause.ai`  
**Jurisdiction:** Republic of India  

*For requests originating under GDPR, CCPA, or DPDPA, please include "Data Subject Rights Request" in the subject line of your email and specify your country/state of residence.*
