Feature: Panel focus
  As a user I want the right panel to fill the viewport so I can work in
  Files without the terminal taking half the screen.

  Scenario: Maximizing the panel gives Files the whole viewport
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I click the "files" tab
    And I click the panel maximize button
    Then I should see the file preview
    And the terminal container is present but hidden

  Scenario: The terminal survives a trip through panel focus
    Given a test session exists
    And I record terminal websocket connections
    And I am on the session page for "e2e-ui-session"
    When I click the panel maximize button
    And I click the panel maximize button
    Then the terminal websocket connected exactly once

  Scenario: Double-clicking a tab toggles the panel fullscreen
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I double-click the "files" tab
    Then I should see the file preview
    And the terminal container is present but hidden
    When I double-click the "files" tab
    Then I should see the terminal container
