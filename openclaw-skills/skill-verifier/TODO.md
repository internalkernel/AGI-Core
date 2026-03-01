# TODO - Inspection Certificates & Escrow Agent

## Product Development Ideas

### Agent Work Marketplace Integration
**Date:** 2026-02-01  
**Context:** After building inspection certificates demo

**Idea:** Mine existing "agent work" marketplaces for:
1. **Example use cases** - Real-world scenarios we can demonstrate
2. **Escrow opportunities** - Offer to be the escrow agent for transactions

**Why this matters:**
- Real marketplaces = real problems to solve
- Inspection Certificates solve Arrow's Information Paradox in these markets
- We can provide trustless escrow using TEE + KMS
- Mining use cases helps us build relevant demos

**Action items:**
- [ ] Research existing agent work marketplaces
- [ ] Document common transaction patterns
- [ ] Identify friction points (where inspection certificates help)
- [ ] Extract 5-10 compelling use cases for demos
- [ ] Consider: Offer escrow-as-a-service to these platforms
- [ ] Build adapters for popular marketplace APIs

**Platforms to investigate:**
- (Add platforms as we discover them)

**Related work:**
- `INSPECTION-CERTIFICATES.md` - Core concept
- `ESCROW-AGENT.md` - Automated escrow architecture
- `ROADMAP.md` - Current development timeline

---

## Other TODOs

### Phase 1 (Current - February Week 1)
- [x] Build interactive web demo
- [x] Fix actual API testing (not just LLM hallucination)
- [ ] Add more inspector types (dataset, TLS transcript)
- [ ] Deploy to public server

### Phase 2 (February Week 2)
- [ ] Deploy to Phala CVM for real TEE attestation
- [ ] Integrate Phala KMS for sealed secrets
- [ ] Build simple escrow MVP

### Phase 3 (February Weeks 3-4)
- [ ] Build marketplace UI
- [ ] User registration + wallet management
- [ ] Browse skills/data listings

### Phase 4 (Month 2)
- [ ] Advanced features (reputation, search, categories)
- [ ] Multi-chain support
- [ ] Analytics dashboard

---

**Remember:** Focus on shipping working examples, not just documentation. The demo is the product.
