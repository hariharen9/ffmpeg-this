# Forget GUIs: How I Built a Powerful Video Editor for the Command Line

![Photo by Kvistholt Photography on Unsplash](https://images.unsplash.com/photo-1598209279122-855128dfa138?ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&ixlib=rb-1.2.1&auto=format&fit=crop&w=1650&q=80)

We’ve all been there. You just need to trim the first five seconds of a screen recording, convert a `.mkv` file to a web-friendly `.mp4`, or join two clips together. You sigh, click the icon for your heavyweight video editor, and wait… and wait… as a massive application loads, just for a two-minute task.

What if you could do all of that and more without ever leaving the comfort and speed of your terminal? 

That question led me to create **peg_this**, a powerful, intuitive command-line video editing suite built with Python and powered by the legendary FFmpeg.

## The Power of the Terminal

For developers and power users, the command line is home. It’s fast, efficient, scriptable, and light on resources. While GUIs are great for complex, creative tasks, they can be overkill for the everyday chores of video manipulation. 

`peg_this` was born from this philosophy: to bring the most common, practical video editing tasks to the command line in a user-friendly, interactive way.

## Introducing `peg_this`

At its heart, `peg_this` is a friendly wrapper around FFmpeg. It transforms complex, hard-to-remember commands into a simple, menu-driven experience. No more searching for that one specific FFmpeg flag on Stack Overflow!

When you run the tool, you’re greeted with a clean, straightforward menu:

```text
What would you like to do?
❯ Process a Single Media File
  Join Multiple Videos
  Batch Convert All Media in Directory
  Exit
```

From here, you can dive into a whole suite of editing features.

## The Feature-Packed Toolkit

`peg_this` isn't just a converter; it's a multi-tool for all your media needs.

### 1. Join Videos—Without the Headache

One of the most requested features was the ability to join clips. But as anyone who has used FFmpeg knows, concatenating files can be tricky if their resolutions or codecs don't match. 

`peg_this` handles this automatically. It intelligently inspects the first video and standardizes the resolution and audio rate of all subsequent clips before joining, ensuring a smooth, error-free result.

```text
? Select at least two videos to join in order: (Press <space> to select, <a> to toggle all, <i> to invert selection)
❯ ◯ clip_A.mp4
  ◯ clip_B.mkv
  ◯ final_scene.mov
```

### 2. Visual Cropping: The GUI in Your CLI

This is the standout feature. How do you crop a video accurately without seeing it? Simple: you generate a preview! The “Crop Video (Visual)” option extracts a frame from the video and opens a simple window. You just click and drag to draw the exact rectangle you want to keep.

![Visual Crop Preview](https://i.imgur.com/your-image-here.png)  
*(Note: You can replace this with a real screenshot of the cropping tool in action!)*

Close the window, and `peg_this` runs the precise FFmpeg command for you. It’s the perfect blend of CLI efficiency and visual feedback.

### 3. Effortless Conversion & Trimming

Of course, the basics are covered. You can convert to a huge range of formats (`mp4`, `mkv`, `webm`, `mp3`, `gif`, etc.) with simple quality presets. Trimming is just as easy, asking you for a start and end time to create a lossless cut in seconds.

### 4. Full-Scale Batch Processing

Need to convert a whole folder of videos for a web project? The batch conversion tool will process every media file in the current directory, saving you an enormous amount of time and effort.

## Under the Hood

For the curious, `peg_this` is built on a foundation of fantastic open-source Python libraries:

-   **`ffmpeg-python`**: A clean, Pythonic interface for FFmpeg.
-   **`rich`**: For the beautiful, modern terminal UI elements.
-   **`questionary`**: For the simple and intuitive interactive prompts.
-   **`Pillow` & `tkinter`**: The magic behind the visual cropping tool.

## Get Started Today!

Ready to give it a spin? It’s easy to get started.

**1. Prerequisite: Install FFmpeg**

You first need FFmpeg on your system. You can download it from the official site: [ffmpeg.org](https://ffmpeg.org/download.html).

**2. Install `peg_this`**

With FFmpeg installed, clone the repository and install the package using `pip`:

```bash
# Clone the repository from GitHub
git clone https://github.com/harishss/peg_this.git

# Navigate into the project directory
cd peg_this

# Install the package
pip install .
```

**3. Run It!**

That’s it! The `peg_this` command is now available system-wide. Just type it in your terminal to launch the application.

```bash
peg_this
```

## The Future is Open

`peg_this` is a tool I built to solve my own problems, and I’m sharing it in the hope that it solves yours too. It’s open-source, and I welcome contributions, feature ideas, and bug reports.

Check out the project on [**GitHub**](https://github.com/harishss/peg_this) and help shape the future of this command-line video suite.

Happy editing!
