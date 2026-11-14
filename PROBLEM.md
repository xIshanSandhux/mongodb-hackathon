# Pull Request Impact Analysis and Regression Testing

When a pull request changes a shared component, reviewers need to know what else might break and which tests will catch it. That information is spread across source files, imports, call sites, and test suites. Running the full suite can slow feedback, while running only the tests closest to the changed files can miss regressions elsewhere.

We want a CI agent that turns a pull request into an explainable test plan. It should identify potentially affected code, select and run relevant regression tests, and tell reviewers why those tests were chosen. If it cannot account for the impact of a change, it should run a broader suite.

## Proposed approach

1. **Map the repository.** Split source files into meaningful chunks, such as functions and classes. Store their embeddings for semantic search and record known relationships between code and tests in a dependency graph queryable in MongoDB Atlas.
2. **Trace the impact of the PR.** Start with the changed files and symbols. Follow graph relationships to find affected code and tests, then use semantic search to surface candidates that explicit relationships may miss.
3. **Run tests and explain the results.** Report which tests ran, why they were selected, what failed, and when uncertainty triggered a broader run.

The first version focuses on test selection and reporting. A follow-up can surface findings from defensive security checks and suggest focused code cleanup for reviewer approval.

## How we will judge success

Replay past pull requests and compare selected tests with results from the full suite. Measure how many known failing tests the selection catches, how many tests it runs, and how long it takes to return results. Record misses and check whether reviewers can understand the reasons given for each selection.
