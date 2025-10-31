# 🎸 GH Chart Reducer

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/downloads/)

**Automatic difficulty generator for Clone Hero and Guitar Hero** with intelligent adaptive reduction algorithm.

Takes a MIDI or .chart file with Expert difficulty and automatically generates Hard, Medium, and Easy difficulties while maintaining playability and preserving special events like Star Power.

---

## ✨ Key Features

- 🎯 **Adaptive Reduction**: Automatically adjusts to each instrument's density
- 🎸 **Multi-Instrument**: Processes Guitar, Bass, Drums, and Keys simultaneously
- ⭐ **Preserves Star Power**: Keeps Star Power sections in their original positions
- 🎵 **Maintains Tracks**: Preserves VOCALS, tempos, events, and synchronization
- 🎮 **Smart Chords**: Reduces chords by keeping the closest notes
- 📊 **Target Percentages**:
  - **Hard**: ~60-65% of Expert (5 buttons, max 2-note chords)
  - **Medium**: ~45-55% of Expert (4 buttons, single notes)
  - **Easy**: ~25-35% of Expert (3 buttons, single notes)

---

## 🚀 Installation

### Requirements

- Python 3.7 or higher
- tkinter (included in most Python installations)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/vsmuggling2023/chart-reducer.git
cd gh-chart-reducer

# Run the application
python reducer.py
```

No external dependencies required - just standard Python!

---

## 📖 Usage

1. **Run the application**:
   ```bash
   python reducer.py
   ```

2. **Load your file**:
   - Click "📂 Load .chart / .mid"
   - Select your file with Expert difficulty

3. **Generate difficulties**:
   - Review detected instruments
   - Click "⚙️ Generate Difficulties"
   - Save the processed file

4. **Done!** Import the file into Clone Hero and play

---

## 🎮 Supported Formats

| Format | Read | Write | Notes |
|---------|---------|-----------|-------|
| `.mid` | ✅ | ✅ | Preserves VOCALS and special events |
| `.chart` | ✅ | ✅ | Clone Hero native format |

---

## 🧠 Reduction Algorithm

The algorithm uses **adaptive spacing** based on the actual Expert density:

```python
# For each difficulty, calculate minimum spacing between notes
median_spacing = calculate_median(expert_spacings)

SPACING_MULTIPLIER = {
    'Hard': 1.01,    # Almost identical to Expert
    'Medium': 2.00,  # Double spacing
    'Easy': 3.33     # Triple spacing
}

min_spacing = median_spacing × multiplier
```

This ensures the reduction is **proportional to the original density** of each instrument, resulting in balanced and playable difficulties.

### Advantages Over Fixed Methods:
- ✅ Adapts to slow and fast songs
- ✅ Maintains the original song's "feel"
- ✅ Consistent results across different files
- ✅ No manual adjustments needed

---

## 🛠️ Technical Features

- **Complete MIDI parsing**: Reads and writes binary MIDI files without dependencies
- **Variable Length Encoding**: Correct MIDI timing handling
- **Event preservation**: Maintains Meta Events, System Exclusive, etc.
- **Multi-difficulty tracks**: Generates MIDI tracks with all difficulties
- **Smart chord reduction**: Maintains harmony and playability

---

## 📝 Use Cases

### For Charters:
- ✅ Speeds up the process of creating lower difficulties
- ✅ Solid foundation that you can manually adjust later
- ✅ Maintains consistency between instruments

### For Players:
- ✅ Create easier versions of your favorite songs
- ✅ Practice on Medium before jumping to Expert
- ✅ Share complete charts with the community

---

## 🐛 Report Bugs

Found a bug? [Open an issue](https://github.com/yourusername/gh-chart-reducer/issues) with:
- Problem description
- Example MIDI/chart file (if possible)
- Steps to reproduce
- Operating system and Python version

---

## 🙏 Acknowledgments

- Clone Hero community for format documentation
- Guitar Hero World Tour for reduction algorithm inspiration

---

## 🎵 Happy Charting!

If this project helped you, consider giving it a ⭐ on GitHub. Thanks!

---

<div align="center">
  
**[⬆ Back to top](#-gh-chart-reducer)**

Made with ❤️ for the Clone Hero community

</div>
