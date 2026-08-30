/**********************************************************************

  Audacity: A Digital Audio Editor

  AudacityMessageBox.cpp

  Paul Licameli split this out of ErrorDialog.cpp

**********************************************************************/

#include "AudacityMessageBox.h"
#include "Internat.h"

#include "Journal.h"
#include "wxArrayStringEx.h"

#include <cstdio>

namespace {
bool sBatchMode = true; // this binary never shows UI

int BatchReplyForStyle(long style)
{
   // Save-on-close is YES_NO|CANCEL — NO discards and lets Exit: finish.
   if (style & wxYES_NO)
      return wxNO;
   return wxOK;
}
}

void SetAudacityBatchMode(bool enabled)
{
   sBatchMode = enabled;
}

bool IsAudacityBatchMode()
{
   return sBatchMode;
}

void AudacityBatchLog(const wxString& channel, const wxString& text)
{
   const wxString line = wxString::Format(
      wxT("audacity-for-agents: %s: %s\n"), channel, text);
   const auto utf8 = line.ToUTF8();
   fwrite(utf8.data(), 1, utf8.length(), stderr);
   fflush(stderr);
}

int AudacityMessageBox(const TranslatableString& message,
   const TranslatableString& caption,
   long style, wxWindow *parent, int x, int y)
{
   if (IsAudacityBatchMode())
   {
      AudacityBatchLog(
         caption.Translation(),
         message.Translation());
      return BatchReplyForStyle(style);
   }

   // wxMessageBox is implemented with native message boxes and does not
   // use the wxWidgets message machinery.  Therefore the wxEventFilter that
   // most journal recording relies on fails us here.  So if replaying, don't
   // really make the modal dialog, but just return the expected value.
   return Journal::IfNotPlaying( L"MessageBox", [&]{
      return ::wxMessageBox(
         message.Translation(), caption.Translation(),
         style, parent, x, y);
   } );
}
