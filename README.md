# Cache Hierarchy Simulator

Final project — Computer Architecture & OS  
Topic #8: Cache Hierarchy Simulator

## Team

| Member | Part |
|---|---|
| Person #1 | Core engine (`core/`) |
| Person #2 | Trace generation & 3C analysis (`traces/`) |
| Person #3 | CLI & experiments (`cli.py`, `experiments/`) |
| Person #4 | Visualization (`viz/`) |
| Person #5 | Presentation |
| Person #6 | Presentation |

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Interactive dashboard

```bash
pip install -r requirements.txt
streamlit run app.py
```

This dashboard uses the existing core simulation, trace generator, and visualization modules to let you tune cache sizes, associativity, replacement policy, and trace patterns in a polished GUI.

## AI tools used

See [AI_USAGE.md](AI_USAGE.md).
