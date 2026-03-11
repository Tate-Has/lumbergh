Feature: Session Files
  As a user I want to browse files in my session's working directory.

  Scenario: File browser shows project files
    Given I am on the session page for "e2e-ui-session"
    When I click the "files" tab
    Then I should see at least one file entry
    And I should see a file named "README.md"
