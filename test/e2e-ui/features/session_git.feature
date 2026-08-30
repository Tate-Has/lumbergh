Feature: Session Git
  As a user I want to view git status and history for my session.

  Scenario: Git tab shows diff and history
    Given I am on the session page for "e2e-ui-session"
    When I click the "git" tab
    Then I should see the git tab content
    And I should see at least one diff file item

  Scenario: Filtering the graph dims commits that do not match
    Given I am on the session page for "e2e-ui-session"
    When I click the "git" tab
    And I search the graph for "Initial"
    Then I should see a match count in the graph toolbar
    And I should see at least one dimmed commit row

  Scenario: Clearing the search restores every commit
    Given I am on the session page for "e2e-ui-session"
    When I click the "git" tab
    And I search the graph for "zzz-no-such-commit"
    And I clear the graph search
    Then I should see no dimmed commit rows

  Scenario: Searching all history finds commits the graph has not loaded
    Given I am on the session page for "e2e-ui-session"
    When I click the "git" tab
    And I search the graph for "Initial"
    And I click the all-history search button
    Then I should see the history search panel

  Scenario: Shift-selecting two commits shows the diff between them
    Given I am on the session page for "e2e-ui-session"
    When I click the "git" tab
    And I click the first commit in the graph
    And I shift-click the last commit in the graph
    Then I should see a compare range header in the diff viewer
