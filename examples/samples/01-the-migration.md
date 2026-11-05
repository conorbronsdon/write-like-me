We moved the billing service off the old queue on a Tuesday. I picked Tuesday because nothing ever happens on a Tuesday. That was the plan, anyway.

By ten the dashboards looked fine. By eleven they looked too fine, which is its own kind of alarm. Nobody's error rate drops to zero after a migration. Ours did. So I went looking, and it turned out the new consumer was swallowing failures and logging them at debug level, where no human has ever looked.

Here's the thing I keep coming back to. The code review passed. The tests passed. Two people I trust signed off. Every check we had was a check that could only say yes.

I don't think the fix is more review. I think it's checks that are built to fail, and a habit of asking what a green light would look like if it were lying. We added one test that night: kill the downstream, confirm the alert fires. It fired. I slept.

If you run a team, try it this week. Pick your favorite dashboard and break the thing it watches. You'll learn more in ten minutes than in a quarter of status meetings.
