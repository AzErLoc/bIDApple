# 🍎 bIDApple - Bad Apple in Your IDA Pro Navband 🎶

> Ever looked at IDA’s navigation band and thought, “This needs *more Touhou*”?  
> **bIDApple** brings the iconic *Bad Apple!!* shadow art video right into IDA Pro's navband.

![bad-apple-gif](https://i.pinimg.com/originals/11/3c/37/113c37e46e35619ae54f555f1d7cc92e.gif)  
*Yes, really. It plays in the navband.*

---

## 🤔 Why?

Because reverse engineering is hard?  
Because sometimes you need a break? 
But mostly because *Bad Apple*.

---

## 💻 What Is This?

**bIDApple** is a (mostly useless but extremely cool) IDA Pro plugin that hijacks the navigation band and turns it into a video player (sadly for the sound I had to cheat a bit and use ffplay because QtMultimedia isn't built into IDA). It streams a preprocessed version of *Bad Apple!!* and renders it frame-by-frame right in IDA’s UI.

Yes, this is a stupid idea.  
Yes, it actually works.

---

## ⚙️ Installation

1. Clone this repo into your IDA plugins directory:

```bash
git clone https://github.com/AzErLoc/bIDApple ~/.idapro/plugins/
```
2. Open IDA Pro.
3. Right click in decompilation or disassembly view.
4. Click the entry to start bIDApple Animation
5. Make your navband bigger 😉

---

## 📽️ Demo
[![bIDApple : Bad Apple in IDA Pro's navband](https://img.youtube.com/vi/NsirMRKIwXE/0.jpg)](https://www.youtube.com/watch?v=NsirMRKIwXE)
