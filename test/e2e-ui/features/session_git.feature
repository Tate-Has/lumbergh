Feature: Session Git
  As a user I want to view git status and history for my session.

  Scenario: Git tab shows diff and history
    Given I am on the session page for "e2e-ui-session"
    When I click the "git" tab
    Then I should see the git tab content
    And I should see at least one diff file item
