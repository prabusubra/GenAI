# Expense Tracker App – Roadmap

**Stack:** React (Cloudflare Pages) · FastAPI (one small instance) · Supabase (PostgreSQL + auth) · pdfplumber/camelot for PDF parsing

---

## Phase 0: Setup and Learning (2–3 weeks)

1. Learn FastAPI basics: routes, Pydantic models, file uploads
2. Set up Supabase project: database tables and auth
3. Create React app with login via Supabase
4. Design tables: `accounts`, `statements`, `transactions`, `categories`, `rules`
5. Build a parser for **one bank statement** and **one credit card statement**, including password-protected PDFs

**✅ Done when:** your own two statements parse into the database correctly

---

## Phase 1: MVP for You (4–6 weeks)

1. Upload page → parse → save transactions
2. Tag each transaction:
   - **Payment method:** Credit Card, Debit Card, UPI, Net Banking, ATM/Cash
   - **Type:** Spend, Income, Transfer, Refund, Fee
3. **Transfer detection:** credit card bill payments and ATM withdrawals are not counted as spend
4. **ATM withdrawals → Cash wallet**, shown as "Cash spend – Uncategorized"; optional split and quick-add cash expenses
5. Decode UPI and debit card POS/ECOM lines into merchant names
6. Auto-categorize with keyword rules; manual edits saved as new rules
7. Dashboard: total spend, by category, by payment method
8. **50/30/20 card** on combined spend

**✅ Done when:** you use it every month instead of a spreadsheet

---

## Phase 2: Friends Beta (4–6 weeks)

1. Parsers for 5–8 more banks and card issuers
2. Credit card details: billing cycle, due date, minimum vs. total due
3. **Money leak finder:** subscriptions, duplicates, interest, late fees, forex markup, annual fees, ATM charges
4. **Monthly Spend Wrapped** shareable card
5. Privacy: delete PDFs after parsing, encrypt sensitive fields, privacy page
6. Feedback button

**✅ Done when:** 10–20 friends upload at least 2 months of statements

---

## Phase 3: Insights (6–8 weeks)

1. **Money Score:** 50/30/20 + credit utilization + emergency fund months
2. Credit utilization per card, with alerts above 30%
3. EMI/BNPL tracker
4. Payment-mix and month-over-month trends
5. Money Rule cards with "Rule of the Month"
6. Savings challenges and streaks

**✅ Done when:** friends return monthly without reminders

---

## Phase 4: Growth (Ongoing)

1. Credit card reward optimizer
2. Email-forward statement import
3. Mobile app (React Native)
4. Legal/DPDP review → public launch
5. Account Aggregator integration

---

## Budget

| Phase      | Estimated Cost                                 |
| ---------- | ---------------------------------------------- |
| Phases 0–1 | ~₹0 (free tiers + domain ~₹800–1,500/year)     |
| Phases 2–3 | ~₹1,000–3,000/month                            |
| Phase 4    | Varies (app store fees, legal review, scaling) |

---

## Key Risks

- **Double counting:** handle card payments, ATM withdrawals and refunds from day one
- **Parser maintenance:** one pluggable parser per bank/card issuer
- **Cash visibility:** keep cash quick-add frictionless
- **Trust and compliance:** review DPDP Act obligations before onboarding friends
