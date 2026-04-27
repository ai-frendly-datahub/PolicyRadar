# PolicyRadar Data Sources Research

**Generated:** 2026-03-04  
**Research Duration:** 10m 33s

## 2026-04-11 Data Quality Overlay

- `policy.yaml` now separates operational event models: `public_consultation`, `enforcement_action`, `policy_effective_date`, `platform_policy_change`, and `security_classification_framework`.
- Key official sources carry freshness and canonical-key metadata: White House, SEC, CFPB, NIST, GovInfo, FTC, EPA, FDA, EUR-Lex, UK/Canada parliament feeds, FSC, PIPC, and KISA.
- `source_backlog` keeps higher-effort candidates inactive until parser, ToS, privacy, and diff-hash checks are complete: Regulations.gov API, lawmaking.go.kr, FTC cases, PIPC disposition archive, and platform policy pages.
- N2SF/CSAP/FIPS 199/FedRAMP 20x tracking must keep official 3-level classification separate from the internal operational overlay described in `docs/n2sf-classification-applicability.md`.

## Executive Summary

PolicyRadar tracks government policies, legislation, regulations, and public policy news across federal, state, and international jurisdictions. The research identified 40+ high-quality sources including official government APIs (Congress.gov, Federal Register), policy news RSS feeds, and think tank publications.

---

## RSS Feeds (20+ sources)

### Official Government RSS Feeds

1. **GovInfo Congressional Bills** - `https://www.govinfo.gov/rss/congressional-bills.xml`
   - Focus: Congressional bills, legislative text
   - Update frequency: Daily
   - Quality: High (Official US GPO)

2. **GovInfo Federal Register** - `https://www.govinfo.gov/rss/federal-register.xml`
   - Focus: Federal regulations, rules
   - Update frequency: Daily
   - Quality: High (Official publication)

3. **Grants.gov New Opportunities** - `https://www.grants.gov/rss/GG_NewOppByCategory.xml`
   - Focus: Federal grant opportunities
   - Update frequency: Daily
   - Quality: High (Official source)

4. **FTC RSS Feeds** - `https://www.ftc.gov/news-events/stay-connected/ftc-rss-feeds`
   - Focus: Consumer protection policy
   - Update frequency: Weekly
   - Quality: High (Official FTC)

5. **Federal Reserve Board RSS** - `https://federalreserve.gov/feeds/feeds.htm`
   - Focus: Monetary policy, regulations
   - Update frequency: Weekly
   - Quality: High (Official Fed)

6. **EPA News Feeds** - `https://www.epa.gov/newsroom/rss-feed.xml`
   - Focus: Environmental policy, regulations
   - Update frequency: Daily
   - Quality: High (Official EPA)

7. **State Department RSS** - `https://www.state.gov/rss-feeds`
   - Focus: Foreign policy, treaties
   - Update frequency: Weekly
   - Quality: High (Official State Dept)

8. **NASA RSS** - `https://www.nasa.gov/rss/dyn/breaking_news.rss`
   - Focus: Space policy, NASA budget
   - Update frequency: Daily
   - Quality: High (Official NASA)

### Policy News RSS Feeds

9. **The Hill** - `https://thehill.com/rss-feed/`
   - Focus: Congressional news, policy coverage
   - Update frequency: Multiple daily
   - Quality: High (T2_professional)

10. **POLITICO Congress** - `https://rss.app/feeds/politico-congress.xml`
    - Focus: Legislative tracking, insider reporting
    - Update frequency: Multiple daily
    - Quality: High (T2_professional)

11. **Punchbowl News** - `https://link.punchbowl.news/rss-feeds/`
    - Focus: Congress-focused news
    - Update frequency: Daily
    - Quality: High (T2_professional)

### Think Tank RSS Feeds

12. **Brookings Institution** - Multiple feeds via FeedSpot
    - Focus: Policy research, economic studies
    - Update frequency: Weekly
    - Quality: High (T2_expert)

13. **Cato Institute** - `https://www.cato.org/blog`
    - Focus: Libertarian policy analysis
    - Update frequency: Weekly
    - Quality: High (T2_expert)

14. **Heritage Foundation** - `https://www.heritage.org/`
    - Focus: Conservative policy analysis
    - Update frequency: Weekly
    - Quality: High (T2_expert)

### Legal News RSS Feeds

15. **Above the Law** - `https://abovethelaw.com`
    - Focus: Legal news, Supreme Court
    - Update frequency: Daily
    - Quality: Medium (T3_professional)

16. **ABA Journal** - `https://www.abajournal.com/stay_connected/item/rss_feeds`
    - Focus: Legal profession, court decisions
    - Update frequency: Daily
    - Quality: High (T2_professional)

17. **Law.com** - `http://feeds.feedblitz.com/law/legal-news/`
    - Focus: Legal news, regulatory updates
    - Update frequency: Daily
    - Quality: High (T2_professional)

18. **JD Supra** - `http://jdsupra.com/legal-news/rss-law-feeds.aspx`
    - Focus: Topical legal news (30+ categories)
    - Update frequency: Daily
    - Quality: Medium (T3_professional)

---

## APIs (6+ sources)

### Congress.gov API
- **Base URL**: `https://api.congress.gov/v3/`
- **Documentation**: https://api.congress.gov/
- **Authentication**: Required (free API key)
- **Key Endpoints**:
  - `/v3/bill` - Search bills, get bill details
  - `/v3/amendment` - Search amendments
  - `/v3/committee` - Committee meetings, materials
  - `/v3/member` - Member information
  - `/v3/summary` - Bill summaries
- **Quality**: Excellent (Official Library of Congress API)
- **GitHub Examples**:
  - LibraryOfCongress/api.congress.gov (official Python client)
  - OpenBB-finance/OpenBB (provider implementation)
  - AshwinSundar/congress_gov_mcp (MCP server)

### Federal Register API
- **Base URL**: `https://www.federalregister.gov/api/v1/`
- **Documentation**: https://www.federalregister.gov/developer
- **Authentication**: Not required
- **Key Endpoints**:
  - `/documents.json` - Search Federal Register documents
  - `/public-inspection.json` - Documents pending publication
  - `/agencies.json` - List federal agencies
  - `/presidential-documents.json` - Executive orders
- **Quality**: High (Official publication)

### PolicyNote API (FiscalNote)
- **Base URL**: `https://fiscalnote.com/products/policynote-api`
- **Documentation**: https://fiscalnote.com/products/policynote-api
- **Authentication**: Required (commercial)
- **Features**:
  - Legislative/regulatory tracking (Congress, 50 states, 100+ countries)
  - Bill summaries, stakeholder tracking
  - AI-powered policy intelligence
  - MCP support
- **Quality**: Very High (commercial, comprehensive)

### Quorum API
- **Base URL**: `https://www.quorum.us/products/quorum-api/`
- **Documentation**: https://quorum.redoc.ly/tag/Bills/
- **Authentication**: Required (commercial)
- **Key Endpoints**:
  - `/api/newbill/` - Bills dataset
  - `/api/member/` - Member information
  - `/api/stakeholder/` - Stakeholder data
- **Quality**: High (commercial)

### Data.gov
- **Base URL**: `https://data.gov/`
- **Documentation**: https://data.gov/
- **Authentication**: Not required
- **Features**:
  - 394,023+ datasets
  - Government spending, demographics, economic indicators
- **Quality**: High (official open data portal)

### ProPublica Congress API
- **Base URL**: `https://propublica.github.io/congress-api-docs/`
- **Documentation**: https://propublica.github.io/congress-api-docs/
- **Authentication**: Not required (rate-limited)
- **Key Endpoints**:
  - `/congress/{congress}/members` - Members of Congress
  - `/members/{bioguide_id}/votes` - Voting record
- **Quality**: High (journalism-focused)

---

## Web Scraping Targets (10+ sites)

### Government Agency Pages

1. **Whitehouse.gov Presidential Actions** - `https://www.whitehouse.gov/presidential-actions/`
   - Target: Executive orders, proclamations
   - Data format: HTML (structured)
   - Update frequency: Weekly

2. **Congress.gov Bills** - `https://www.congress.gov/bill`
   - Target: Bill text, committee reports
   - Data format: HTML
   - Update frequency: Daily

3. **Regulations.gov** - `https://www.regulations.gov/`
   - Target: Proposed regulations, public comments
   - Data format: HTML
   - Update frequency: Daily

4. **FederalRegister.gov** - `https://www.federalregister.gov/documents/current`
   - Target: Federal regulations, proposed rules
   - Data format: HTML
   - Update frequency: Daily

5. **State.gov Press Releases** - `https://www.state.gov/press-releases/`
   - Target: Diplomatic statements, foreign policy
   - Data format: HTML
   - Update frequency: Weekly

### Agency News Pages

6. **EPA News Releases** - `https://www.epa.gov/newsroom/browse-news-releases`
   - Target: Environmental regulations, enforcement
   - Data format: HTML tables
   - Update frequency: Weekly

7. **NASA Policy Reports** - `https://www.nasa.gov/about/policy/`
   - Target: Space policy, funding announcements
   - Data format: HTML/PDF
   - Update frequency: Monthly

### Think Tank Research

8. **Brookings Research** - `https://www.brookings.edu/research/`
   - Target: Policy research papers, expert analysis
   - Data format: HTML
   - Update frequency: Weekly

9. **Heritage.org Reports** - `https://www.heritage.org/reports/`
   - Target: Conservative policy briefs
   - Data format: HTML
   - Update frequency: Weekly

10. **Cato.org Publications** - `https://www.cato.org/publications`
    - Target: Libertarian policy analysis
    - Data format: HTML
    - Update frequency: Weekly

---

## Recommended Configuration

### High Priority (Real-time Official Sources)

```yaml
policy_official:
  - name: "Congress.gov API"
    url: "https://api.congress.gov/v3"
    type: "api"
    auth_required: true
    priority: 1
    focus: "Legislative tracking"
  
  - name: "Federal Register API"
    url: "https://www.federalregister.gov/api/v1"
    type: "api"
    auth_required: false
    priority: 2
    focus: "Regulatory tracking"
  
  - name: "GovInfo Congressional Bills RSS"
    url: "https://www.govinfo.gov/rss/congressional-bills.xml"
    type: "rss"
    priority: 3
    focus: "Bill updates"
```

### Medium Priority (Policy News)

```yaml
policy_news:
  - name: "The Hill RSS"
    url: "https://thehill.com/rss-feed/"
    type: "rss"
    priority: 4
    focus: "Congressional news"
  
  - name: "POLITICO Congress RSS"
    url: "https://rss.app/feeds/politico-congress.xml"
    type: "rss"
    priority: 5
    focus: "Legislative tracking"
```

### Web Scraping (Backup/Supplemental)

```yaml
policy_scraping:
  - name: "Whitehouse.gov"
    url: "https://www.whitehouse.gov/presidential-actions/"
    type: "scrape"
    priority: 6
    focus: "Executive orders"
  
  - name: "Brookings Research"
    url: "https://www.brookings.edu/research/"
    type: "scrape"
    priority: 7
    focus: "Policy research"
```

---

## Implementation Recommendations

1. **Start with Congress.gov API** - Core legislative tracking
2. **Add Federal Register API** - Regulatory tracking
3. **Implement RSS collectors** for news sources
4. **Web scraping** for think tank research (with rate limiting)
5. **Commercial APIs** (FiscalNote, Quorum) if budget allows

### Entity Extraction
- **Legislation**: Bill numbers, sponsors, cosponsors, committees
- **Regulations**: Agency, docket number, effective date
- **Policy Topics**: Keywords, policy areas, impact statements
- **Actors**: Members of Congress, agencies, think tanks

### Data Storage Schema
```sql
CREATE TABLE legislation (
    id TEXT PRIMARY KEY,
    congress INT,
    bill_number TEXT,
    title TEXT,
    summary TEXT,
    sponsor TEXT,
    status TEXT,
    introduced_date DATE,
    url TEXT,
    collected_at TIMESTAMP
);

CREATE TABLE regulations (
    id TEXT PRIMARY KEY,
    docket_number TEXT,
    title TEXT,
    agency TEXT,
    document_type TEXT,
    effective_date DATE,
    comment_deadline DATE,
    collected_at TIMESTAMP
);
```

---

## Notes

- **Congress.gov API** requires free API key registration
- **Federal Register API** is completely open (no auth required)
- **Commercial APIs** (FiscalNote, Quorum) have pricing tiers
- All government RSS feeds are in public domain
- Think tank data usage may require attribution

**Total Sources**: 20+ RSS, 6+ APIs, 10+ Scraping Targets
