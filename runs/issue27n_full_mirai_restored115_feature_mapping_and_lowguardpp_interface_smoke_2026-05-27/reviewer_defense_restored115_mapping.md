# Reviewer Defense: restored115 Mapping

**Q1: Why not run on the 115D matrix directly?**
Because a 115D shape match is not enough. Without feature names/order, we cannot know whether common100 and extra15 are correctly identified.

**Q2: Why drop col0?**
The first column is a strict row index and is strongly correlated with labels only because the file is ordered benign-first/attack-later.

**Q3: Is this a method failure?**
No. It is an input-schema and prior-use gate. The method has not been evaluated under clean restored115 yet.

**Q4: What blocks a clean split?**
The historical my_gold prefix appears to contain all benign rows. Strictly excluding prior-use rows leaves no benign data.

**Q5: What should happen next?**
Recover feature-name/order mapping or use the timestamped official 100k asset if its mapping and overlap can be resolved.
