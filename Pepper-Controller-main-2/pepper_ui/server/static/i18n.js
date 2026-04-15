/* ================================================================
   i18n.js – Pepper Medical Assistant – Bilingual (EN / AR)
   ES5-strict, no const/let/arrow/template-literals, Chrome 37 safe
   ================================================================ */
(function (root) {
  "use strict";

  /* ---- translation dictionary ---- */
  var T = {
    /* ---------- index.html ---------- */
    "hello_pepper":       { en: "Hello, I am Pepper",           ar: "\u0645\u0631\u062d\u0628\u0627\u060c \u0623\u0646\u0627 \u0628\u064a\u0628\u0631" },
    "your_medical_guide": { en: "Your medical guide.",           ar: "\u0645\u0631\u0634\u062f\u0643 \u0627\u0644\u0637\u0628\u064a." },
    "tap_to_speak":       { en: "Tap to Speak",                  ar: "\u0627\u0636\u063a\u0637 \u0644\u0644\u062a\u062d\u062f\u062b" },
    "sign_in":            { en: "Sign In",                       ar: "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644" },
    "sign_up":            { en: "Sign Up",                       ar: "\u0625\u0646\u0634\u0627\u0621 \u062d\u0633\u0627\u0628" },
    "logout":             { en: "Logout",                        ar: "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062e\u0631\u0648\u062c" },
    "staff_dashboard":    { en: "Staff Dashboard",               ar: "\u0644\u0648\u062d\u0629 \u0627\u0644\u0645\u0648\u0638\u0641\u064a\u0646" },
    "hello_user":         { en: "Hello, ",                       ar: "\u0645\u0631\u062d\u0628\u0627\u060c " },
    "book_appointment":   { en: "Book Appointment",              ar: "\u062d\u062c\u0632 \u0645\u0648\u0639\u062f" },
    "check_schedule":     { en: "Check Schedule",                ar: "\u0627\u0644\u062c\u062f\u0648\u0644 \u0627\u0644\u0632\u0645\u0646\u064a" },
    "my_appointments":    { en: "My Appointments",               ar: "\u0645\u0648\u0627\u0639\u064a\u062f\u064a" },
    "emergency":          { en: "Emergency",                     ar: "\u0637\u0648\u0627\u0631\u0626" },
    "guide_to_room":      { en: "Guide to Room",                ar: "\u0627\u0644\u062f\u0644\u064a\u0644 \u0625\u0644\u0649 \u0627\u0644\u063a\u0631\u0641\u0629" },
    "health_tips":        { en: "Health Tips",                   ar: "\u0646\u0635\u0627\u0626\u062d \u0635\u062d\u064a\u0629" },
    "chat_faq":           { en: "Chat / FAQ",                    ar: "\u0645\u062d\u0627\u062f\u062b\u0629 / \u0623\u0633\u0626\u0644\u0629" },
    "about":              { en: "About",                         ar: "\u0639\u0646 \u0628\u064a\u0628\u0631" },
    "symptom_check":      { en: "Symptom Check",                 ar: "\u0641\u062d\u0635 \u0627\u0644\u0623\u0639\u0631\u0627\u0636" },
    "page_x_of_y":        { en: "Page {0} / {1}",               ar: "\u0635\u0641\u062d\u0629 {0} / {1}" },
    "footer":             { en: "Andalusia Hospital \u2014 Powered by Pepper", ar: "\u0645\u0633\u062a\u0634\u0641\u0649 \u0623\u0646\u062f\u0644\u0633\u064a\u0629 \u2014 \u0628\u0648\u0627\u0633\u0637\u0629 \u0628\u064a\u0628\u0631" },

    /* ---------- voice overlay ---------- */
    "initializing":       { en: "Initializing...",               ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u062a\u0647\u064a\u0626\u0629..." },
    "ready":              { en: "Ready",                         ar: "\u062c\u0627\u0647\u0632" },
    "connecting":         { en: "Connecting...",                 ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u0627\u062a\u0635\u0627\u0644..." },
    "listening":          { en: "Listening...",                  ar: "\u0623\u0633\u062a\u0645\u0639..." },
    "thinking":           { en: "Thinking...",                   ar: "\u0623\u0641\u0643\u0631..." },
    "processing":         { en: "Processing...",                 ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629..." },
    "voice_greeting":     { en: "Hello, I'm Pepper. Tap below to chat.", ar: "\u0645\u0631\u062d\u0628\u0627\u060c \u0623\u0646\u0627 \u0628\u064a\u0628\u0631. \u0627\u0636\u063a\u0637 \u0644\u0644\u0645\u062d\u0627\u062f\u062b\u0629." },
    "stop_recording":     { en: "Stop Recording",               ar: "\u0625\u064a\u0642\u0627\u0641 \u0627\u0644\u062a\u0633\u062c\u064a\u0644" },
    "waiting_robot":      { en: "(Waiting for robot connection...)", ar: "(\u0641\u064a \u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u062a\u0635\u0627\u0644 \u0627\u0644\u0631\u0648\u0628\u0648\u062a...)" },
    "listening_to_you":   { en: "(Listening to you...)",         ar: "(\u0623\u0633\u062a\u0645\u0639 \u0625\u0644\u064a\u0643...)" },
    "thinking_dots":      { en: "(Thinking...)",                 ar: "(\u0623\u0641\u0643\u0631...)" },
    "you_said":           { en: "You: \"{0}\"",                  ar: "\u0623\u0646\u062a: \"{0}\"" },
    "pepper_said":        { en: "Pepper: \"{0}\"",               ar: "\u0628\u064a\u0628\u0631: \"{0}\"" },
    "new_badge":          { en: "NEW",                           ar: "\u062c\u062f\u064a\u062f" },

    /* ---------- chat.html ---------- */
    "chat_title":         { en: "Chat with Pepper",              ar: "\u0645\u062d\u0627\u062f\u062b\u0629 \u0645\u0639 \u0628\u064a\u0628\u0631" },
    "type_message":       { en: "Type your message...",          ar: "\u0627\u0643\u062a\u0628 \u0631\u0633\u0627\u0644\u062a\u0643..." },
    "send":               { en: "Send",                          ar: "\u0625\u0631\u0633\u0627\u0644" },
    "chat_greeting":      { en: "Hello! I am Pepper, your medical assistant. How can I help you today?", ar: "\u0645\u0631\u062d\u0628\u0627! \u0623\u0646\u0627 \u0628\u064a\u0628\u0631\u060c \u0645\u0633\u0627\u0639\u062f\u0643 \u0627\u0644\u0637\u0628\u064a. \u0643\u064a\u0641 \u064a\u0645\u0643\u0646\u0646\u064a \u0645\u0633\u0627\u0639\u062f\u062a\u0643 \u0627\u0644\u064a\u0648\u0645\u061f" },

    /* ---------- guide.html ---------- */
    "guide_title":        { en: "Guide to Room",                 ar: "\u0627\u0644\u062f\u0644\u064a\u0644 \u0625\u0644\u0649 \u0627\u0644\u063a\u0631\u0641\u0629" },
    "search_doctor":      { en: "Search doctor...",              ar: "\u0627\u0628\u062d\u062b \u0639\u0646 \u0637\u0628\u064a\u0628..." },
    "navigate":           { en: "Navigate",                      ar: "\u0627\u0628\u062f\u0623 \u0627\u0644\u062a\u0648\u062c\u064a\u0647" },
    "navigating_to":      { en: "Navigating to {0}...",          ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u062a\u0648\u062c\u064a\u0647 \u0625\u0644\u0649 {0}..." },
    "cancel_nav":         { en: "Cancel Navigation",             ar: "\u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062a\u0648\u062c\u064a\u0647" },

    /* ---------- about.html ---------- */
    "about_title":        { en: "About Pepper",                  ar: "\u0639\u0646 \u0628\u064a\u0628\u0631" },
    "about_intro":        { en: "Let me introduce myself. I am Pepper, your medical assistant at Andalusia Hospital.", ar: "\u062f\u0639\u0646\u064a \u0623\u0639\u0631\u0641\u0643 \u0628\u0646\u0641\u0633\u064a. \u0623\u0646\u0627 \u0628\u064a\u0628\u0631\u060c \u0645\u0633\u0627\u0639\u062f\u0643 \u0627\u0644\u0637\u0628\u064a \u0641\u064a \u0645\u0633\u062a\u0634\u0641\u0649 \u0623\u0646\u062f\u0644\u0633\u064a\u0629." },

    /* ---------- emergency.html ---------- */
    "emergency_title":    { en: "Emergency",                     ar: "\u0637\u0648\u0627\u0631\u0626" },
    "hold_to_alert":      { en: "Press and hold to alert staff", ar: "\u0627\u0636\u063a\u0637 \u0645\u0639 \u0627\u0644\u0627\u0633\u062a\u0645\u0631\u0627\u0631 \u0644\u062a\u0646\u0628\u064a\u0647 \u0627\u0644\u0645\u0648\u0638\u0641\u064a\u0646" },
    "alert_sent":         { en: "Alert Sent!",                   ar: "\u062a\u0645 \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u062a\u0646\u0628\u064a\u0647!" },

    /* ---------- schedule.html ---------- */
    "schedule_title":     { en: "Doctor Schedule",               ar: "\u062c\u062f\u0648\u0644 \u0627\u0644\u0623\u0637\u0628\u0627\u0621" },
    "no_schedule":        { en: "No schedule found.",            ar: "\u0644\u0627 \u064a\u0648\u062c\u062f \u062c\u062f\u0648\u0644." },

    /* ---------- book.html ---------- */
    "book_title":         { en: "Book an Appointment",           ar: "\u062d\u062c\u0632 \u0645\u0648\u0639\u062f" },
    "select_doctor":      { en: "Select Doctor",                 ar: "\u0627\u062e\u062a\u0631 \u0627\u0644\u0637\u0628\u064a\u0628" },
    "select_date":        { en: "Select Date",                   ar: "\u0627\u062e\u062a\u0631 \u0627\u0644\u062a\u0627\u0631\u064a\u062e" },
    "select_time":        { en: "Select Time",                   ar: "\u0627\u062e\u062a\u0631 \u0627\u0644\u0648\u0642\u062a" },
    "confirm_booking":    { en: "Confirm Booking",               ar: "\u062a\u0623\u0643\u064a\u062f \u0627\u0644\u062d\u062c\u0632" },
    "booking_confirmed":  { en: "Booking Confirmed!",            ar: "\u062a\u0645 \u062a\u0623\u0643\u064a\u062f \u0627\u0644\u062d\u062c\u0632!" },

    /* ---------- tips.html ---------- */
    "tips_title":         { en: "Health Tips",                   ar: "\u0646\u0635\u0627\u0626\u062d \u0635\u062d\u064a\u0629" },

    /* ---------- appointments.html ---------- */
    "appointments_title": { en: "My Appointments",               ar: "\u0645\u0648\u0627\u0639\u064a\u062f\u064a" },
    "no_appointments":    { en: "No upcoming appointments.",     ar: "\u0644\u0627 \u062a\u0648\u062c\u062f \u0645\u0648\u0627\u0639\u064a\u062f \u0642\u0627\u062f\u0645\u0629." },
    "cancel":             { en: "Cancel",                        ar: "\u0625\u0644\u063a\u0627\u0621" },

    /* ---------- login.html ---------- */
    "login_title":        { en: "Sign In",                       ar: "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644" },
    "user_id":            { en: "User ID",                       ar: "\u0631\u0642\u0645 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645" },
    "password":           { en: "Password",                      ar: "\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631" },
    "login_btn":          { en: "Sign In",                       ar: "\u062f\u062e\u0648\u0644" },
    "no_account":         { en: "Don't have an account?",        ar: "\u0644\u064a\u0633 \u0644\u062f\u064a\u0643 \u062d\u0633\u0627\u0628\u061f" },
    "create_account":     { en: "Create Account",                ar: "\u0625\u0646\u0634\u0627\u0621 \u062d\u0633\u0627\u0628" },

    /* ---------- signup.html ---------- */
    "signup_title":       { en: "Create Account",                ar: "\u0625\u0646\u0634\u0627\u0621 \u062d\u0633\u0627\u0628" },
    "full_name":          { en: "Full Name",                     ar: "\u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0643\u0627\u0645\u0644" },
    "confirm_password":   { en: "Confirm Password",              ar: "\u062a\u0623\u0643\u064a\u062f \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631" },
    "register":           { en: "Register",                      ar: "\u062a\u0633\u062c\u064a\u0644" },
    "have_account":       { en: "Already have an account?",      ar: "\u0644\u062f\u064a\u0643 \u062d\u0633\u0627\u0628 \u0628\u0627\u0644\u0641\u0639\u0644\u061f" },

    /* ---------- staff_dashboard.html ---------- */
    "dashboard_title":    { en: "Staff Dashboard",               ar: "\u0644\u0648\u062d\u0629 \u0627\u0644\u0645\u0648\u0638\u0641\u064a\u0646" },

    /* ---------- guide.html (extra) ---------- */
    "find_your_doctor":   { en: "Find Your Doctor",              ar: "\u0627\u0628\u062d\u062b \u0639\u0646 \u0637\u0628\u064a\u0628\u0643" },
    "guide_subtitle":     { en: "Tap a doctor below and Pepper will guide you to their room.", ar: "\u0627\u0636\u063a\u0637 \u0639\u0644\u0649 \u0627\u0644\u0637\u0628\u064a\u0628 \u0648\u0633\u064a\u0631\u0634\u062f\u0643 \u0628\u064a\u0628\u0631 \u0625\u0644\u0649 \u063a\u0631\u0641\u062a\u0647." },
    "connecting_robot":   { en: "Connecting to robot\u2026",     ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u0627\u062a\u0635\u0627\u0644 \u0628\u0627\u0644\u0631\u0648\u0628\u0648\u062a\u2026" },
    "robot_connected":    { en: "Robot connected. Loading directory\u2026", ar: "\u062a\u0645 \u0627\u0644\u0627\u062a\u0635\u0627\u0644. \u062c\u0627\u0631\u064a \u062a\u062d\u0645\u064a\u0644 \u0627\u0644\u062f\u0644\u064a\u0644\u2026" },
    "robot_offline":      { en: "Robot offline. Showing directory (navigation disabled).", ar: "\u0627\u0644\u0631\u0648\u0628\u0648\u062a \u063a\u064a\u0631 \u0645\u062a\u0635\u0644. \u0639\u0631\u0636 \u0627\u0644\u062f\u0644\u064a\u0644 (\u0627\u0644\u062a\u0648\u062c\u064a\u0647 \u0645\u0639\u0637\u0644)." },
    "select_doctor_guide":{ en: "Select a doctor below. Pepper will guide you.", ar: "\u0627\u062e\u062a\u0631 \u0637\u0628\u064a\u0628\u064b\u0627. \u0628\u064a\u0628\u0631 \u0633\u064a\u0631\u0634\u062f\u0643." },
    "guiding_to":         { en: "Pepper is guiding you to {0}. Please follow the robot.", ar: "\u0628\u064a\u0628\u0631 \u064a\u0631\u0634\u062f\u0643 \u0625\u0644\u0649 {0}. \u064a\u0631\u062c\u0649 \u0645\u062a\u0627\u0628\u0639\u0629 \u0627\u0644\u0631\u0648\u0628\u0648\u062a." },
    "arrived_doctor":     { en: "Arrived at {0}. The doctor will see you shortly.", ar: "\u0648\u0635\u0644\u0646\u0627 \u0625\u0644\u0649 {0}. \u0633\u064a\u0631\u0627\u0643 \u0627\u0644\u0637\u0628\u064a\u0628 \u0642\u0631\u064a\u0628\u064b\u0627." },
    "nav_blocked":        { en: "Navigation blocked. Please ask staff for assistance.", ar: "\u0627\u0644\u062a\u0648\u062c\u064a\u0647 \u0645\u062d\u0638\u0648\u0631. \u064a\u0631\u062c\u0649 \u0637\u0644\u0628 \u0627\u0644\u0645\u0633\u0627\u0639\u062f\u0629." },
    "connection_lost":    { en: "Connection lost. Please ask staff for assistance.", ar: "\u0627\u0646\u0642\u0637\u0639 \u0627\u0644\u0627\u062a\u0635\u0627\u0644. \u064a\u0631\u062c\u0649 \u0637\u0644\u0628 \u0627\u0644\u0645\u0633\u0627\u0639\u062f\u0629." },
    "robot_nav_offline":  { en: "Robot is offline. Navigation is not available.", ar: "\u0627\u0644\u0631\u0648\u0628\u0648\u062a \u063a\u064a\u0631 \u0645\u062a\u0635\u0644. \u0627\u0644\u062a\u0648\u062c\u064a\u0647 \u063a\u064a\u0631 \u0645\u062a\u0627\u062d." },
    "loading_directory":  { en: "Loading doctor directory\u2026", ar: "\u062c\u0627\u0631\u064a \u062a\u062d\u0645\u064a\u0644 \u062f\u0644\u064a\u0644 \u0627\u0644\u0623\u0637\u0628\u0627\u0621\u2026" },
    "no_doctors_found":   { en: "No doctors found in directory.", ar: "\u0644\u0627 \u064a\u0648\u062c\u062f \u0623\u0637\u0628\u0627\u0621 \u0641\u064a \u0627\u0644\u062f\u0644\u064a\u0644." },
    "retry":              { en: "Retry",                          ar: "\u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629" },
    "guide_footer":       { en: "Andalusia Hospital \u2014 Pepper Navigation System", ar: "\u0645\u0633\u062a\u0634\u0641\u0649 \u0623\u0646\u062f\u0644\u0633\u064a\u0629 \u2014 \u0646\u0638\u0627\u0645 \u062a\u0648\u062c\u064a\u0647 \u0628\u064a\u0628\u0631" },

    /* ---------- about.html (extra) ---------- */
    "i_am_pepper":        { en: "I am Pepper",                   ar: "\u0623\u0646\u0627 \u0628\u064a\u0628\u0631" },
    "healthcare_asst":    { en: "Your Personal Healthcare Assistant", ar: "\u0645\u0633\u0627\u0639\u062f\u0643 \u0627\u0644\u0635\u062d\u064a \u0627\u0644\u0634\u062e\u0635\u064a" },
    "my_mission":         { en: "My Mission",                    ar: "\u0645\u0647\u0645\u062a\u064a" },
    "mission_text":       { en: "I am here to make your visit to Andalusia Hospital smoother and friendlier. I use advanced AI to help you find doctors, book appointments, and answer your questions instantly.", ar: "\u0623\u0646\u0627 \u0647\u0646\u0627 \u0644\u062c\u0639\u0644 \u0632\u064a\u0627\u0631\u062a\u0643 \u0644\u0645\u0633\u062a\u0634\u0641\u0649 \u0623\u0646\u062f\u0644\u0633\u064a\u0629 \u0623\u0633\u0647\u0644 \u0648\u0623\u0644\u0637\u0641. \u0623\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a \u0644\u0645\u0633\u0627\u0639\u062f\u062a\u0643 \u0641\u064a \u0625\u064a\u062c\u0627\u062f \u0627\u0644\u0623\u0637\u0628\u0627\u0621 \u0648\u062d\u062c\u0632 \u0627\u0644\u0645\u0648\u0627\u0639\u064a\u062f \u0648\u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0639\u0644\u0649 \u0623\u0633\u0626\u0644\u062a\u0643." },
    "what_i_can_do":      { en: "What I Can Do",                 ar: "\u0645\u0627 \u064a\u0645\u0643\u0646\u0646\u064a \u0641\u0639\u0644\u0647" },
    "technical_specs":    { en: "Technical Specs",               ar: "\u0627\u0644\u0645\u0648\u0627\u0635\u0641\u0627\u062a \u0627\u0644\u062a\u0642\u0646\u064a\u0629" },
    "about_footer":       { en: "Designed for Andalusia Hospital \u2014 AAST Graduation Project 2025.", ar: "\u0645\u0635\u0645\u0645 \u0644\u0645\u0633\u062a\u0634\u0641\u0649 \u0623\u0646\u062f\u0644\u0633\u064a\u0629 \u2014 \u0645\u0634\u0631\u0648\u0639 \u062a\u062e\u0631\u062c AAST 2025." },

    /* ---------- emergency.html (extra) ---------- */
    "emergency_help":     { en: "Emergency Help",                ar: "\u0645\u0633\u0627\u0639\u062f\u0629 \u0637\u0648\u0627\u0631\u0626" },
    "emergency_subtitle": { en: "If you are in a medical emergency, press and hold to notify the team.", ar: "\u0625\u0630\u0627 \u0643\u0646\u062a \u0641\u064a \u062d\u0627\u0644\u0629 \u0637\u0648\u0627\u0631\u0626 \u0637\u0628\u064a\u0629\u060c \u0627\u0636\u063a\u0637 \u0645\u0639 \u0627\u0644\u0627\u0633\u062a\u0645\u0631\u0627\u0631 \u0644\u0625\u0628\u0644\u0627\u063a \u0627\u0644\u0641\u0631\u064a\u0642." },
    "call_emergency":     { en: "CALL EMERGENCY",                ar: "\u0627\u062a\u0635\u0644 \u0628\u0627\u0644\u0637\u0648\u0627\u0631\u0626" },
    "hold_2_sec":         { en: "Press & hold for 2 seconds",    ar: "\u0627\u0636\u063a\u0637 \u0644\u0645\u062f\u0629 \u062b\u0627\u0646\u064a\u062a\u064a\u0646" },
    "help_sent":          { en: "HELP SENT!",                    ar: "\u062a\u0645 \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0645\u0633\u0627\u0639\u062f\u0629!" },
    "staff_notified":     { en: "Alert sent. Staff has been notified.", ar: "\u062a\u0645 \u0627\u0644\u062a\u0646\u0628\u064a\u0647. \u062a\u0645 \u0625\u062e\u0637\u0627\u0631 \u0627\u0644\u0645\u0648\u0638\u0641\u064a\u0646." },
    "back_to_home":       { en: "\u2190 Back to Home",           ar: "\u2192 \u0627\u0644\u0639\u0648\u062f\u0629 \u0644\u0644\u0631\u0626\u064a\u0633\u064a\u0629" },

    /* ---------- schedule.html (extra) ---------- */
    "department":         { en: "Department",                    ar: "\u0627\u0644\u0642\u0633\u0645" },
    "doctor":             { en: "Doctor",                        ar: "\u0627\u0644\u0637\u0628\u064a\u0628" },
    "select_department":  { en: "Select Department",             ar: "\u0627\u062e\u062a\u0631 \u0627\u0644\u0642\u0633\u0645" },
    "select_dept_first":  { en: "Select Department First",       ar: "\u0627\u062e\u062a\u0631 \u0627\u0644\u0642\u0633\u0645 \u0623\u0648\u0644\u0627\u064b" },
    "select_a_doctor":    { en: "Select a doctor to see their schedule.", ar: "\u0627\u062e\u062a\u0631 \u0637\u0628\u064a\u0628\u064b\u0627 \u0644\u0639\u0631\u0636 \u062c\u062f\u0648\u0644\u0647." },
    "schedule_for":       { en: "Schedule for {0}:",             ar: "\u062c\u062f\u0648\u0644 {0}:" },

    /* ---------- book.html (extra) ---------- */
    "patient_name":       { en: "Patient Name",                  ar: "\u0627\u0633\u0645 \u0627\u0644\u0645\u0631\u064a\u0636" },
    "date":               { en: "Date",                          ar: "\u0627\u0644\u062a\u0627\u0631\u064a\u062e" },
    "time":               { en: "Time",                          ar: "\u0627\u0644\u0648\u0642\u062a" },
    "step_1_dept":        { en: "1 Department",                  ar: "1 \u0627\u0644\u0642\u0633\u0645" },
    "step_2_doctor":      { en: "2 Doctor",                      ar: "2 \u0627\u0644\u0637\u0628\u064a\u0628" },
    "step_3_datetime":    { en: "3 Date & Time",                 ar: "3 \u0627\u0644\u062a\u0627\u0631\u064a\u062e \u0648\u0627\u0644\u0648\u0642\u062a" },
    "step_4_confirm":     { en: "4 Confirm",                     ar: "4 \u062a\u0623\u0643\u064a\u062f" },
    "fill_all_fields":    { en: "Please fill all fields.",       ar: "\u064a\u0631\u062c\u0649 \u0645\u0644\u0621 \u062c\u0645\u064a\u0639 \u0627\u0644\u062d\u0642\u0648\u0644." },
    "booking_dots":       { en: "Booking...",                    ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u062d\u062c\u0632..." },
    "appointment_confirmed": { en: "Appointment Confirmed!",     ar: "\u062a\u0645 \u062a\u0623\u0643\u064a\u062f \u0627\u0644\u0645\u0648\u0639\u062f!" },
    "booking_failed":     { en: "Booking Failed: {0}",           ar: "\u0641\u0634\u0644 \u0627\u0644\u062d\u062c\u0632: {0}" },

    /* ---------- tips.html (extra) ---------- */
    "tips_subtitle":      { en: "Personalized AI recommendations for you...", ar: "\u062a\u0648\u0635\u064a\u0627\u062a \u0630\u0643\u064a\u0629 \u0645\u062e\u0635\u0635\u0629 \u0644\u0643..." },
    "recommended_for":    { en: "Recommended for {0}",           ar: "\u0645\u0648\u0635\u0649 \u0628\u0647 \u0644\u0640 {0}" },
    "generating_tips":    { en: "Generating personalized tips based on your case...", ar: "\u062c\u0627\u0631\u064a \u0625\u0639\u062f\u0627\u062f \u0646\u0635\u0627\u0626\u062d \u0645\u062e\u0635\u0635\u0629 \u0644\u062d\u0627\u0644\u062a\u0643..." },

    /* ---------- appointments.html (extra) ---------- */
    "sign_in_to_view":    { en: "Please sign in to see your appointments.", ar: "\u064a\u0631\u062c\u0649 \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644 \u0644\u0639\u0631\u0636 \u0645\u0648\u0627\u0639\u064a\u062f\u0643." },
    "no_appointments_found": { en: "No appointments found.",     ar: "\u0644\u0627 \u062a\u0648\u062c\u062f \u0645\u0648\u0627\u0639\u064a\u062f." },

    /* ---------- login.html (extra) ---------- */
    "enter_id_pass":      { en: "Enter your ID and Password.",   ar: "\u0623\u062f\u062e\u0644 \u0631\u0642\u0645\u0643 \u0648\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631." },
    "patient":            { en: "Patient",                       ar: "\u0645\u0631\u064a\u0636" },
    "staff":              { en: "Staff",                         ar: "\u0645\u0648\u0638\u0641" },
    "id_number":          { en: "ID Number",                     ar: "\u0631\u0642\u0645 \u0627\u0644\u0647\u0648\u064a\u0629" },
    "verifying":          { en: "Verifying...",                  ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u062a\u062d\u0642\u0642..." },
    "enter_id_password":  { en: "Please enter ID and Password.", ar: "\u064a\u0631\u062c\u0649 \u0625\u062f\u062e\u0627\u0644 \u0627\u0644\u0631\u0642\u0645 \u0648\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631." },

    /* ---------- signup.html (extra) ---------- */
    "register_new":       { en: "Register as a new user.",       ar: "\u0633\u062c\u0644 \u0643\u0645\u0633\u062a\u062e\u062f\u0645 \u062c\u062f\u064a\u062f." },
    "login_id":           { en: "ID Number (Login ID)",          ar: "\u0631\u0642\u0645 \u0627\u0644\u0647\u0648\u064a\u0629 (\u0631\u0642\u0645 \u0627\u0644\u062f\u062e\u0648\u0644)" },
    "create_password":    { en: "Create Password",               ar: "\u0625\u0646\u0634\u0627\u0621 \u0643\u0644\u0645\u0629 \u0645\u0631\u0648\u0631" },
    "case_number":        { en: "Patient Case Number (optional)", ar: "\u0631\u0642\u0645 \u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u0631\u064a\u0636 (\u0627\u062e\u062a\u064a\u0627\u0631\u064a)" },
    "fields_required":    { en: "Name, ID, and Password are required.", ar: "\u0627\u0644\u0627\u0633\u0645 \u0648\u0627\u0644\u0631\u0642\u0645 \u0648\u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631 \u0645\u0637\u0644\u0648\u0628\u0629." },
    "creating":           { en: "Creating...",                   ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u0625\u0646\u0634\u0627\u0621..." },
    "account_created":    { en: "Account Created! Please Sign In.", ar: "\u062a\u0645 \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u062d\u0633\u0627\u0628! \u064a\u0631\u062c\u0649 \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644." },

    /* ---------- staff_dashboard.html (extra) ---------- */
    "logged_in_as":       { en: "Logged in as: {0} (Staff)",     ar: "\u062a\u0645 \u0627\u0644\u062f\u062e\u0648\u0644 \u0643\u0640: {0} (\u0645\u0648\u0638\u0641)" },
    "appointments_tab":   { en: "Appointments",                  ar: "\u0627\u0644\u0645\u0648\u0627\u0639\u064a\u062f" },
    "emergency_tab":      { en: "Emergency",                     ar: "\u0627\u0644\u0637\u0648\u0627\u0631\u0626" },
    "doctors_tab":        { en: "Doctors",                       ar: "\u0627\u0644\u0623\u0637\u0628\u0627\u0621" },
    "schedule_tab":       { en: "Schedule",                      ar: "\u0627\u0644\u062c\u062f\u0648\u0644" },
    "patients_tab":       { en: "Patients",                      ar: "\u0627\u0644\u0645\u0631\u0636\u0649" },
    "refresh":            { en: "Refresh",                       ar: "\u062a\u062d\u062f\u064a\u062b" },
    "clear_all":          { en: "Clear All",                     ar: "\u0645\u0633\u062d \u0627\u0644\u0643\u0644" },
    "add_doctor":         { en: "Add Doctor",                    ar: "\u0625\u0636\u0627\u0641\u0629 \u0637\u0628\u064a\u0628" },
    "name":               { en: "Name",                          ar: "\u0627\u0644\u0627\u0633\u0645" },
    "room":               { en: "Room",                          ar: "\u0627\u0644\u063a\u0631\u0641\u0629" },
    "doctors_list":       { en: "Doctors List",                  ar: "\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0623\u0637\u0628\u0627\u0621" },
    "remove":             { en: "Remove",                        ar: "\u062d\u0630\u0641" },
    "edit_schedule":      { en: "Edit Doctor Schedule",          ar: "\u062a\u0639\u062f\u064a\u0644 \u062c\u062f\u0648\u0644 \u0627\u0644\u0637\u0628\u064a\u0628" },
    "day":                { en: "Day",                           ar: "\u0627\u0644\u064a\u0648\u0645" },
    "start":              { en: "Start",                         ar: "\u0627\u0644\u0628\u062f\u0627\u064a\u0629" },
    "end":                { en: "End",                           ar: "\u0627\u0644\u0646\u0647\u0627\u064a\u0629" },
    "add_row":            { en: "Add Row",                       ar: "\u0625\u0636\u0627\u0641\u0629 \u0633\u0637\u0631" },
    "save_schedule":      { en: "Save Schedule",                 ar: "\u062d\u0641\u0638 \u0627\u0644\u062c\u062f\u0648\u0644" },
    "current_schedule":   { en: "Current Schedule",              ar: "\u0627\u0644\u062c\u062f\u0648\u0644 \u0627\u0644\u062d\u0627\u0644\u064a" },
    "pepper_chat":        { en: "Pepper Chat",                   ar: "\u0645\u062d\u0627\u062f\u062b\u0629 \u0628\u064a\u0628\u0631" },

    /* ---------- shared / nav ---------- */
    "back":               { en: "\u2190 Back",                   ar: "\u2192 \u0631\u062c\u0648\u0639" },
    "home":               { en: "Home",                          ar: "\u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629" },
    "loading":            { en: "Loading...",                    ar: "\u062c\u0627\u0631\u064a \u0627\u0644\u062a\u062d\u0645\u064a\u0644..." },
    "error_occurred":     { en: "An error occurred.",            ar: "\u062d\u062f\u062b \u062e\u0637\u0623." },
    "ok":                 { en: "OK",                            ar: "\u0645\u0648\u0627\u0641\u0642" },
    "yes":                { en: "Yes",                           ar: "\u0646\u0639\u0645" },
    "no":                 { en: "No",                            ar: "\u0644\u0627" },
    "close":              { en: "Close",                         ar: "\u0625\u063a\u0644\u0627\u0642" },

    /* ---------- nav_bridge / MainVoice TTS ---------- */
    "please_speak":       { en: "Please speak now.",             ar: "\u062a\u0641\u0636\u0644 \u0628\u0627\u0644\u062a\u062d\u062f\u062b \u0627\u0644\u0622\u0646." },
    "arrived_at":         { en: "We have arrived. This is {0}.", ar: "\u0644\u0642\u062f \u0648\u0635\u0644\u0646\u0627. \u0647\u0630\u0627 \u0647\u0648 {0}." },
    "nav_cancelled":      { en: "Navigation cancelled.",         ar: "\u062a\u0645 \u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062a\u0648\u062c\u064a\u0647." },

    /* ---------- qr_checkin.html ---------- */
    "qr_checkin":         { en: "QR Check-In",                   ar: "\u062a\u0633\u062c\u064a\u0644 \u0628\u0640QR" },
    "qr_title":           { en: "Quick Check-In",                ar: "\u062a\u0633\u062c\u064a\u0644 \u0633\u0631\u064a\u0639" },
    "qr_subtitle":        { en: "Show this QR code at reception for fast check-in.", ar: "\u0627\u0639\u0631\u0636 \u0631\u0645\u0632 QR \u0647\u0630\u0627 \u0641\u064a \u0627\u0644\u0627\u0633\u062a\u0642\u0628\u0627\u0644 \u0644\u062a\u0633\u062c\u064a\u0644 \u0633\u0631\u064a\u0639." },
    "qr_not_logged_in":   { en: "Please sign in to generate your check-in QR code.", ar: "\u064a\u0631\u062c\u0649 \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644 \u0644\u0625\u0646\u0634\u0627\u0621 \u0631\u0645\u0632 QR." },
    "qr_patient_id":      { en: "Patient ID: {0}",               ar: "\u0631\u0642\u0645 \u0627\u0644\u0645\u0631\u064a\u0636: {0}" },
    "qr_name":            { en: "Name: {0}",                     ar: "\u0627\u0644\u0627\u0633\u0645: {0}" },
    "qr_case":            { en: "Case: {0}",                     ar: "\u0627\u0644\u062d\u0627\u0644\u0629: {0}" },

    /* ---------- analytics tab ---------- */
    "analytics_tab":      { en: "Analytics",                     ar: "\u0627\u0644\u0625\u062d\u0635\u0627\u0626\u064a\u0627\u062a" },
    "total_appointments":  { en: "Total Appointments",           ar: "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0648\u0627\u0639\u064a\u062f" },
    "total_patients":      { en: "Total Patients",               ar: "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0631\u0636\u0649" },
    "total_doctors":       { en: "Total Doctors",                ar: "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0623\u0637\u0628\u0627\u0621" },
    "total_emergencies":   { en: "Total Emergencies",            ar: "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0637\u0648\u0627\u0631\u0626" },
    "total_triages":       { en: "Total Triages",                ar: "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0641\u062d\u0648\u0635\u0627\u062a" },
    "triage_distribution": { en: "Triage Level Distribution",    ar: "\u062a\u0648\u0632\u064a\u0639 \u0645\u0633\u062a\u0648\u064a\u0627\u062a \u0627\u0644\u0641\u0631\u0632" },
    "dept_distribution":   { en: "Appointments by Department",   ar: "\u0627\u0644\u0645\u0648\u0627\u0639\u064a\u062f \u062d\u0633\u0628 \u0627\u0644\u0642\u0633\u0645" },
    "export_pdf":          { en: "Export PDF",                   ar: "\u062a\u0635\u062f\u064a\u0631 PDF" },

    /* ---------- conversation memory ---------- */
    "chat_history_cleared": { en: "Chat history cleared.",       ar: "\u062a\u0645 \u0645\u0633\u062d \u0633\u062c\u0644 \u0627\u0644\u0645\u062d\u0627\u062f\u062b\u0629." },
    "clear_chat":          { en: "Clear Chat",                   ar: "\u0645\u0633\u062d \u0627\u0644\u0645\u062d\u0627\u062f\u062b\u0629" },

    /* ---------- appointment reminder ---------- */
    "reminder_upcoming":   { en: "Reminder: You have an appointment with {0} on {1} at {2}.", ar: "\u062a\u0630\u0643\u064a\u0631: \u0644\u062f\u064a\u0643 \u0645\u0648\u0639\u062f \u0645\u0639 {0} \u064a\u0648\u0645 {1} \u0627\u0644\u0633\u0627\u0639\u0629 {2}." }
  };

  /* ---- helper: get current language ---- */
  function getLang() {
    try { return localStorage.getItem("pepper_lang") || "en"; } catch (e) { return "en"; }
  }

  /* ---- helper: set language & persist ---- */
  function setLang(lang) {
    if (lang !== "en" && lang !== "ar") lang = "en";
    try { localStorage.setItem("pepper_lang", lang); } catch (e) {}
  }

  /* ---- translate a key, with optional placeholders ---- */
  function t(key) {
    var lang = getLang();
    var entry = T[key];
    if (!entry) return key;
    var text = entry[lang] || entry["en"] || key;
    /* replace {0}, {1}, ... with extra arguments */
    for (var i = 1; i < arguments.length; i++) {
      text = text.replace("{" + (i - 1) + "}", arguments[i]);
    }
    return text;
  }

  /* ---- apply translations to DOM elements with data-i18n ---- */
  function applyI18n() {
    var lang = getLang();
    /* set html dir and lang */
    document.documentElement.lang = lang;
    document.body.dir = (lang === "ar") ? "rtl" : "ltr";

    /* translate all elements with data-i18n attribute */
    var els = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < els.length; i++) {
      var key = els[i].getAttribute("data-i18n");
      var entry = T[key];
      if (!entry) continue;
      var text = entry[lang] || entry["en"];
      /* handle input placeholders */
      if (els[i].tagName === "INPUT" || els[i].tagName === "TEXTAREA") {
        els[i].placeholder = text;
      } else {
        els[i].textContent = text;
      }
    }

    /* translate elements with data-i18n-html (for innerHTML) */
    var htmlEls = document.querySelectorAll("[data-i18n-html]");
    for (var j = 0; j < htmlEls.length; j++) {
      var hkey = htmlEls[j].getAttribute("data-i18n-html");
      var hentry = T[hkey];
      if (!hentry) continue;
      htmlEls[j].innerHTML = hentry[lang] || hentry["en"];
    }
  }

  /* ---- toggle language ---- */
  function toggleLang() {
    var cur = getLang();
    var next = (cur === "en") ? "ar" : "en";
    setLang(next);
    applyI18n();
    /* update toggle button text */
    var btn = document.getElementById("langToggle");
    if (btn) btn.textContent = (next === "en") ? "\u0639\u0631\u0628\u064a" : "English";
    /* call page-specific refresh if defined */
    if (typeof window.onLangChange === "function") window.onLangChange(next);
  }

  /* ---- expose public API ---- */
  root.I18N = {
    T: T,
    t: t,
    getLang: getLang,
    setLang: setLang,
    applyI18n: applyI18n,
    toggleLang: toggleLang
  };

})(window);
