# Contributing to ffmpeg-this

First off, thank you for considering contributing to ffmpeg-this! It's people like you that make ffmpeg-this such a great tool.

## Where do I go from here?

If you've noticed a bug or have a feature request, [make one](https://github.com/hariharen9/ffmpeg-this/issues/new)! It's generally best if you get confirmation of your bug or approval for your feature request this way before starting to code.

### Fork & create a branch

If this is something you think you can fix, then [fork ffmpeg-this](https://github.com/hariharen9/ffmpeg-this/fork) and create a branch with a descriptive name.

A good branch name would be (where issue #33 is the ticket you're working on):

```sh
git checkout -b 33-add-new-feature
```

### Implement your fix or feature

At this point, you're ready to make your changes! Feel free to ask for help; everyone is a beginner at first :smile_cat:

### Make a Pull Request

At this point, you should switch back to your master branch and make sure it's up to date with ffmpeg-this's master branch:

```sh
git remote add upstream git@github.com:hariharen9/ffmpeg-this.git
git checkout master
git pull upstream master
```

Then update your feature branch from your local copy of master, and push it!

```sh
git checkout 33-add-new-feature
git rebase master
git push --set-upstream origin 33-add-new-feature
```

Finally, go to GitHub and [make a Pull Request](https://github.com/hariharen9/ffmpeg-this/compare) :D

### Keeping your Pull Request updated

If a maintainer asks you to "rebase" your PR, they're saying that a lot of code has changed, and that you need to update your branch so it's easier to merge.

To learn more about rebasing and merging, check out this guide on [merging vs. rebasing](https://www.atlassian.com/git/tutorials/merging-vs-rebasing).

## How to get in touch

If you need help, you can ask on the [issue tracker](https://github.com/hariharen9/ffmpeg-this/issues) or you can email me at [thisishariharen@gmail.com](mailto:thisishariharen@gmail.com).

## Code of Conduct

Everyone interacting in the ffmpeg-this project's codebases, issue trackers, chat rooms, and mailing lists is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
