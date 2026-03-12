# 🚀 QUICK START — What to Do RIGHT NOW

> **Goal:** Get from 85% → 100% in 1-4 weeks  
> **Start Here:** This file  
> **Full Plan:** [COMPLETION_ROADMAP.md](./COMPLETION_ROADMAP.md)

---

## 📍 Where We Are

**Status:** 85% Complete (February 24, 2026)

```
✅ All 41 nodes implemented
✅ Graph architecture complete
✅ LLM client with caching
✅ Model routing system

❌ 0% test coverage (BLOCKER)
❌ Jury not using routing (-85% cost)
❌ Database schema missing
❌ SHINE not functional
```

---

## ⏰ TODAY (Day 1) — First 4 Hours

### Step 1: Setup Environment (30 min)

```bash
# 1. Navigate to project
cd /path/to/deep-research-spec

# 2. Ensure you're on struct branch
git checkout struct
git pull origin struct

# 3. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio

# 5. Setup environment variables
cp .env.example .env
# Edit .env with your API keys:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# DATABASE_URL=postgresql://drs:drs_dev_password@localhost:5432/drs
```

---

### Step 2: Smoke Test (15 min)

```bash
# Test critical imports
python -c "from src.graph.graph import build_graph; print('✓ Graph OK')"
python -c "from src.graph.nodes.writer import writer_node; print('✓ Writer OK')"
python -c "from src.graph.nodes.jury import jury_node; print('✓ Jury OK')"
python -c "from src.llm.client import llm_client; print('✓ LLM Client OK')"
python -c "from src.llm.routing import route_model; print('✓ Routing OK')"

# If ANY fail:
# 1. Check error message for missing module
# 2. pip install <missing-module>
# 3. Repeat until all pass
```

**Expected Output:**
```
✓ Graph OK
✓ Writer OK
✓ Jury OK
✓ LLM Client OK
✓ Routing OK
```

---

### Step 3: Run Test Suite (1 hour)

```bash
# Start PostgreSQL (required for some tests)
docker-compose up -d postgres

# Wait for healthy
docker-compose ps postgres  # Should show "healthy"

# Run all tests
pytest tests/ -v --tb=short --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
# Or: xdg-open htmlcov/index.html  # Linux
# Or: start htmlcov/index.html  # Windows
```

**Expected:** 10-30 failures (this is NORMAL, we'll fix them)

**Common Failures:**

1. **ImportError: No module named 'X'**
   ```bash
   pip install X
   ```

2. **TypeError: X() takes 2 positional arguments but 3 were given**
   - Function signature mismatch
   - Check function definition vs. call

3. **KeyError: 'some_key'**
   - State dictionary missing expected key
   - Add default: `state.get("some_key", default_value)`

4. **Database connection refused**
   ```bash
   docker-compose up -d postgres
   docker-compose logs postgres  # Check for errors
   ```

---

### Step 4: Fix First Bug (1.5 hours)

**Priority: Pick the EASIEST failure first**

```bash
# 1. Pick one failing test
pytest tests/unit/test_writer.py::test_writer_basic -v

# 2. Read error message carefully
# 3. Open relevant file in editor
# 4. Fix the issue
# 5. Re-run test
pytest tests/unit/test_writer.py::test_writer_basic -v

# 6. If passes, commit
git add src/graph/nodes/writer.py
git commit -m "fix(writer): resolve KeyError for missing state key"

# 7. Repeat for next test
```

**Debugging Tips:**

```python
# Add print statements (remove before commit)
print(f"DEBUG: state keys = {state.keys()}")
print(f"DEBUG: value = {state.get('key', 'MISSING')}")

# Use debugger
import pdb; pdb.set_trace()  # Add breakpoint
# Run: pytest tests/unit/test_writer.py -v -s

# Check types
print(f"DEBUG: type(value) = {type(value)}")
```

---

### Step 5: Critical Fix - Jury Routing (1 hour)

**This ONE fix saves 85% of jury costs!**

```bash
# 1. Open jury.py
code src/graph/nodes/jury.py  # Or your editor

# 2. Find lines 19-21 (hardcoded models)
# DELETE:
# _MODEL_R = "openai/o3"
# _MODEL_F = "google/gemini-2.5-pro"
# _MODEL_S = "google/gemini-2.5-flash"

# 3. Add import at top (line 8)
from src.llm.routing import route_model

# 4. Find jury_node function (line ~52)
# REPLACE:
# judges_r = [JudgeR(f"R{i}", _MODEL_R) for i in range(jury_size)]

# WITH:
preset = state.get("quality_preset", "balanced")
model_r = route_model("jury_r", preset)
model_f = route_model("jury_f", preset)
model_s = route_model("jury_s", preset)

judges_r = [JudgeR(f"R{i}", model_r) for i in range(jury_size)]
judges_f = [JudgeF(f"F{i}", model_f) for i in range(jury_size)]
judges_s = [JudgeS(f"S{i}", model_s, style_rules=style_rules) for i in range(jury_size)]

# 5. Save and test
pytest tests/unit/test_jury.py -v

# 6. Commit
git add src/graph/nodes/jury.py
git commit -m "fix(jury): integrate route_model for preset-aware selection

- Jury now respects economy/balanced/premium presets
- Expected cost reduction: -85% on economy preset
- Resolves hardcoded tier3 models"

git push origin struct
```

**Impact:**
```
Before: $3.96 per section (jury)
After (economy): $0.03 per section
Savings: -99% 🚀
```

---

## ✅ END OF DAY 1 CHECKLIST

```
[ ] Environment setup complete
[ ] All imports working (smoke test passed)
[ ] Test suite runs (even with failures)
[ ] At least 1 test fixed and committed
[ ] Jury routing integrated and pushed
[ ] Coverage report generated
```

**If ALL checked:** 🎉 **You're on track!**

**Progress:** 85% → 87% (+2%)

---

## 📅 THIS WEEK (Days 2-5)

### Day 2: Fix Remaining Test Failures (6-8 hours)

```bash
# Goal: All tests passing

# 1. List all failures
pytest tests/ --tb=no -q | grep FAILED > failures.txt
cat failures.txt

# 2. Group by type
# - Import errors (fix first, easiest)
# - Type errors (check function signatures)
# - Key errors (add defaults to state access)
# - Logic errors (requires debugging)

# 3. Fix one category at a time
# 4. Commit after each fix
# 5. Push at end of day

git push origin struct
```

**Target:** 90% test pass rate

---

### Day 3: Database Schema (2 hours)

```bash
# 1. Create schema file
touch docker/init.sql

# 2. Copy schema from COMPLETION_ROADMAP.md (Task 1.3)
# Or:
curl https://raw.githubusercontent.com/lucadidomenicodopehubs/deep-research-spec/struct/docs/COMPLETION_ROADMAP.md | \
  sed -n '/-- File: docker\/init.sql/,/^```$/p' | \
  tail -n +2 | head -n -1 > docker/init.sql

# 3. Update docker-compose.yml to mount init.sql
# (See COMPLETION_ROADMAP Task 1.3)

# 4. Restart PostgreSQL
docker-compose down postgres
docker-compose up -d postgres

# 5. Verify schema
docker exec -it $(docker ps -qf "name=postgres") \
  psql -U drs -d drs -c "\dt"

# Should show: documents, sections, llm_calls, verdicts

# 6. Commit
git add docker/init.sql docker-compose.yml
git commit -m "feat(db): add PostgreSQL schema for checkpoints and metrics"
git push origin struct
```

**Progress:** 87% → 90%

---

### Day 4: Fail-Safe Error Handling (1 hour)

```bash
# 1. Open jury.py
code src/graph/nodes/jury.py

# 2. Find error handler (lines ~85-97)
# CHANGE:
# "pass_fail": True,  # DANGEROUS!

# TO:
# "pass_fail": False,  # Fail closed
# "veto_category": "technical_failure",
# "css_contribution": 0.0,

# 3. Test
pytest tests/unit/test_jury_error_handling.py -v

# 4. Commit
git add src/graph/nodes/jury.py
git commit -m "fix(jury): fail closed on errors instead of auto-approving"
git push origin struct
```

**Progress:** 90% → 92%

---

### Day 5: Integration Test (2 hours)

```bash
# Run end-to-end test
pytest tests/integration/test_pipeline_e2e.py -v -s

# If passes:
git tag v1.0.0-mvp
git push origin v1.0.0-mvp

# Celebrate! 🎉
```

**Progress:** 92% → **95% (MVP READY)**

---

## 🚀 SHIP MVP (End of Week 1)

**What You Have:**
- ✅ All tests passing
- ✅ Jury optimized (-85% cost)
- ✅ Database ready
- ✅ Fail-safe errors
- ✅ Core pipeline working

**What's Missing:**
- SHINE optimization (Phase 2)
- Observability (Phase 2)
- UI (Phase 3)

**Decision Point:**

1. **Ship Now** → MVP in production, iterate later
2. **Week 2** → Add optimizations (recommended)
3. **Weeks 2-3** → Full polish (ideal)

---

## 📚 NEXT STEPS

### If Shipping MVP:
```bash
# 1. Deploy to staging
# 2. Run smoke tests
# 3. Measure cost per document
# 4. Deploy to production
# 5. Monitor for 1 week
```

### If Continuing (Recommended):

**Week 2 Goals:**
- SHINE integration (-40% tokens)
- Prometheus metrics
- Style profiles from config
- Knowledge base build

See: [COMPLETION_ROADMAP.md Phase 2](./COMPLETION_ROADMAP.md#-phase-2-optimizations-week-2--high-roi)

---

## 🎯 KEY METRICS TO TRACK

**Daily:**
```bash
# Test pass rate
pytest tests/ -q | tail -1
# Target: "X passed in Y.Ys"

# Coverage
pytest tests/ --cov=src --cov-report=term | grep TOTAL
# Target: >80%
```

**Weekly:**
- Cost per document (target: <$3.00 MVP, <$1.00 optimized)
- Latency (target: <5 min per section)
- Quality (manual review of 3 outputs)

---

## ❓ TROUBLESHOOTING

**"Tests won't run"**
```bash
# Check Python version
python --version  # Should be 3.11+

# Reinstall deps
pip install --force-reinstall -r requirements.txt

# Clear cache
rm -rf __pycache__ .pytest_cache
pytest tests/ --cache-clear
```

**"Import errors everywhere"**
```bash
# Ensure src/ is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use editable install
pip install -e .
```

**"Database connection fails"**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres

# Reset database
docker-compose down -v postgres
docker-compose up -d postgres
```

**"Jury still using expensive models"**
```bash
# Verify routing.py is imported
python -c "from src.graph.nodes.jury import route_model; print('OK')"

# Check config
cat config/model_routing.yaml

# Debug routing
python -c "
from src.llm.routing import route_model
print('economy:', route_model('jury_r', 'economy'))
print('balanced:', route_model('jury_r', 'balanced'))
print('premium:', route_model('jury_r', 'premium'))
"
```

---

## 📞 GETTING HELP

**Before asking:**
1. Read error message carefully
2. Check [COMPLETION_ROADMAP.md](./COMPLETION_ROADMAP.md) for detailed instructions
3. Search GitHub issues
4. Try troubleshooting steps above

**When asking:**
- Include: Full error message + stack trace
- Include: Output of `pytest tests/ -v --tb=short`
- Include: Your environment (`python --version`, `pip list | grep anthropic`)
- Include: What you already tried

---

## ✅ SUCCESS CRITERIA

**Week 1 Complete When:**
- [ ] `pytest tests/` shows 0 failures
- [ ] `git log --oneline | head -10` shows 10+ commits this week
- [ ] Coverage report shows >60%
- [ ] Jury uses routing (check logs)
- [ ] Database schema exists (`\dt` in psql)
- [ ] MVP tag pushed (`git tag -l` shows v1.0.0-mvp)

**If ALL checked: 🏆 PHASE 1 COMPLETE**

---

## 🔗 IMPORTANT LINKS

- **Full Plan:** [COMPLETION_ROADMAP.md](./COMPLETION_ROADMAP.md)
- **Architecture:** [AI_CODING_PLAN.md](./AI_CODING_PLAN.md)
- **API Docs:** [API.md](./API.md) (once created)
- **GitHub Issues:** [Create Issue](https://github.com/lucadidomenicodopehubs/deep-research-spec/issues/new)

---

**Last Updated:** 2026-02-24  
**Status:** Ready to Start  
**Estimated Time to MVP:** 20-30 hours (1 week)

**🚀 GO GET 'EM!**
