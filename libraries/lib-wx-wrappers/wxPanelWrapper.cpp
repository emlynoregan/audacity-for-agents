//
//  wxPanelWrapper.cpp
//  Audacity
//
//  Created by Paul Licameli on 6/25/16.
//
//

#include "wxPanelWrapper.h"

#include <cstdio>
#include <wx/grid.h>

const TranslatableString wxDirDialogWrapper::DefaultDialogPrompt = XO("Select a directory");

void wxTabTraversalWrapperCharHook(wxKeyEvent &event)
{
//#ifdef __WXMAC__
#if defined(__WXMAC__) || defined(__WXGTK__)
   // Compensate for the regressions in TAB key navigation
   // due to the switch to wxWidgets 3.0.2
   if (event.GetKeyCode() == WXK_TAB) {
      auto focus = wxWindow::FindFocus();
      if (dynamic_cast<wxGrid*>(focus)
         || (focus &&
             focus->GetParent() &&
             dynamic_cast<wxGrid*>(focus->GetParent()->GetParent()))) {
         // Let wxGrid do its own TAB key handling
         event.Skip();
         return;
      }
      // Apparently, on wxGTK, FindFocus can return NULL
      if (focus)
      {
         focus->Navigate(
            event.ShiftDown()
            ? wxNavigationKeyEvent::IsBackward
            :  wxNavigationKeyEvent::IsForward
         );
         return;
      }
   }
#endif

   event.Skip();
}

void wxPanelWrapper::SetLabel(const TranslatableString & label)
{
   wxPanel::SetLabel( label.Translation() );
}

void wxPanelWrapper::SetName(const TranslatableString & name)
{
   wxPanel::SetName( name.Translation() );
}

void wxPanelWrapper::SetToolTip(const TranslatableString &toolTip)
{
   wxPanel::SetToolTip( toolTip.Stripped().Translation() );
}

void wxPanelWrapper::SetName()
{
   wxPanel::SetName( GetLabel() );
}

void wxDialogWrapper::SetTitle(const TranslatableString & title)
{
   wxDialog::SetTitle( title.Translation() );
}

void wxDialogWrapper::SetLabel(const TranslatableString & label)
{
   wxDialog::SetLabel( label.Translation() );
}

void wxDialogWrapper::SetName(const TranslatableString & name)
{
   wxDialog::SetName( name.Translation() );
}

void wxDialogWrapper::SetName()
{
   wxDialog::SetName( wxDialog::GetTitle() );
}

int wxDialogWrapper::ShowModal()
{
   // This binary never shows windows. Callers treat CANCEL / NO as decline.
   const auto title = GetTitle();
   fprintf(stderr,
      "audacity-for-agents: dialog suppressed (ShowModal): %s\n",
      (const char *)title.utf8_str());
   fflush(stderr);
   // CANCEL is the safe universal decline for agents.
   return wxID_CANCEL;
}

bool wxDialogWrapper::Show(bool show)
{
   if (!show)
      return wxDialog::Show(false);
   const auto title = GetTitle();
   fprintf(stderr,
      "audacity-for-agents: dialog suppressed (Show): %s\n",
      (const char *)title.utf8_str());
   fflush(stderr);
   return false;
}

int wxDirDialogWrapper::ShowModal()
{
   fprintf(stderr,
      "audacity-for-agents: dialog suppressed (DirDialog::ShowModal)\n");
   fflush(stderr);
   return wxID_CANCEL;
}

AudacityMessageDialog::~AudacityMessageDialog() = default;
