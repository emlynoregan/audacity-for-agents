#if defined(WIN32)

#define WIN32_LEAN_AND_MEAN  // Exclude rarely-used stuff from Windows headers
#include <windows.h>
#include <stdio.h>
#include <tchar.h>

const int nBuff = 1024;
// How long to wait for the *other* pipe once one side has a client.
const DWORD kConnectTimeoutMs = 15000;

extern "C" int DoSrv( char * pIn );
extern "C" int DoSrvMore( char * pOut, size_t nMax );

static HANDLE CreateAgentsPipe(const TCHAR *name)
{
   // One listening instance per CreateNamedPipe call. Recreate after each
   // client so a failed/partial connect cannot leave ERROR_PIPE_BUSY forever.
   return CreateNamedPipe(
      name,
      PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
      PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
      1, // nMaxInstances — we recreate handles each loop
      nBuff,
      nBuff,
      50, // Timeout - always send straight away.
      NULL);
}

static void CloseAgentsPipe(HANDLE *ph)
{
   if (ph && *ph != INVALID_HANDLE_VALUE)
   {
      CancelIoEx(*ph, NULL);
      FlushFileBuffers(*ph);
      DisconnectNamedPipe(*ph);
      CloseHandle(*ph);
      *ph = INVALID_HANDLE_VALUE;
   }
}

static BOOL ConnectAgentsPipe(HANDLE hPipe, DWORD timeoutMs, DWORD *pErr)
{
   OVERLAPPED ov;
   ZeroMemory(&ov, sizeof(ov));
   ov.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
   if (!ov.hEvent)
   {
      if (pErr)
         *pErr = GetLastError();
      return FALSE;
   }

   BOOL ok = ConnectNamedPipe(hPipe, &ov);
   DWORD err = GetLastError();
   if (ok)
   {
      CloseHandle(ov.hEvent);
      if (pErr)
         *pErr = 0;
      return TRUE;
   }
   if (err == ERROR_PIPE_CONNECTED)
   {
      CloseHandle(ov.hEvent);
      if (pErr)
         *pErr = err;
      return TRUE;
   }
   if (err != ERROR_IO_PENDING)
   {
      CloseHandle(ov.hEvent);
      if (pErr)
         *pErr = err;
      return FALSE;
   }

   DWORD wait = WaitForSingleObject(ov.hEvent, timeoutMs);
   if (wait == WAIT_OBJECT_0)
   {
      DWORD transferred = 0;
      ok = GetOverlappedResult(hPipe, &ov, &transferred, FALSE);
      err = ok ? 0 : GetLastError();
      CloseHandle(ov.hEvent);
      if (pErr)
         *pErr = err;
      return ok || err == ERROR_PIPE_CONNECTED;
   }

   CancelIoEx(hPipe, &ov);
   CloseHandle(ov.hEvent);
   if (pErr)
      *pErr = ERROR_SEM_TIMEOUT;
   return FALSE;
}

void PipeServer()
{
   static const TCHAR pipeNameToSrv[] = _T("\\\\.\\pipe\\ToAudacityForAgents");
   static const TCHAR pipeNameFromSrv[] = _T("\\\\.\\pipe\\FromAudacityForAgents");

   for(;;)
   {
      HANDLE hPipeToSrv = CreateAgentsPipe(pipeNameToSrv);
      if (hPipeToSrv == INVALID_HANDLE_VALUE)
      {
         fprintf(stderr, "audacity-for-agents: pipe: CreateNamedPipe To failed (%lu)\n",
            GetLastError());
         fflush(stderr);
         Sleep(250);
         continue;
      }

      HANDLE hPipeFromSrv = CreateAgentsPipe(pipeNameFromSrv);
      if (hPipeFromSrv == INVALID_HANDLE_VALUE)
      {
         fprintf(stderr, "audacity-for-agents: pipe: CreateNamedPipe From failed (%lu)\n",
            GetLastError());
         fflush(stderr);
         CloseAgentsPipe(&hPipeToSrv);
         Sleep(250);
         continue;
      }

      fprintf(stderr, "audacity-for-agents: pipe: listening\n");
      fflush(stderr);

      // Clients open From (read) first, then To (write). Wait forever for From;
      // once From is up, To must arrive quickly or we recycle (avoids permanent
      // ERROR_PIPE_BUSY after a half-open client).
      DWORD errFrom = 0;
      BOOL bConnectedFrom = ConnectAgentsPipe(
         hPipeFromSrv, INFINITE, &errFrom);
      fprintf(stderr, "audacity-for-agents: pipe: from-srv connected=%i err=%lu\n",
         bConnectedFrom, errFrom);
      fflush(stderr);

      DWORD errTo = 0;
      BOOL bConnectedTo = FALSE;
      if (bConnectedFrom)
      {
         bConnectedTo = ConnectAgentsPipe(
            hPipeToSrv, kConnectTimeoutMs, &errTo);
         fprintf(stderr, "audacity-for-agents: pipe: to-srv connected=%i err=%lu\n",
            bConnectedTo, errTo);
         fflush(stderr);
      }

      if (bConnectedTo && bConnectedFrom)
      {
         for (;;)
         {
            CHAR chRequest[nBuff];
            CHAR chResponse[nBuff];
            DWORD cbBytesRead = 0;
            DWORD cbBytesWritten = 0;
            OVERLAPPED ovRead;
            ZeroMemory(&ovRead, sizeof(ovRead));
            ovRead.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
            if (!ovRead.hEvent)
               break;

            BOOL bSuccess = ReadFile(
               hPipeToSrv, chRequest, nBuff, NULL, &ovRead);
            DWORD err = GetLastError();
            if (!bSuccess && err != ERROR_IO_PENDING)
            {
               CloseHandle(ovRead.hEvent);
               break;
            }
            if (!bSuccess)
            {
               if (WaitForSingleObject(ovRead.hEvent, INFINITE) != WAIT_OBJECT_0)
               {
                  CancelIoEx(hPipeToSrv, &ovRead);
                  CloseHandle(ovRead.hEvent);
                  break;
               }
               bSuccess = GetOverlappedResult(
                  hPipeToSrv, &ovRead, &cbBytesRead, FALSE);
            }
            else
            {
               GetOverlappedResult(hPipeToSrv, &ovRead, &cbBytesRead, FALSE);
            }
            CloseHandle(ovRead.hEvent);

            if (!bSuccess || cbBytesRead == 0)
               break;

            if (cbBytesRead >= nBuff)
               cbBytesRead = nBuff - 1;
            chRequest[cbBytesRead] = '\0';

            DoSrv(chRequest);
            while (true)
            {
               int nWritten = DoSrvMore(chResponse, nBuff);
               if (nWritten <= 1)
                  break;
               OVERLAPPED ovWrite;
               ZeroMemory(&ovWrite, sizeof(ovWrite));
               ovWrite.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
               if (!ovWrite.hEvent)
                  break;
               BOOL wOk = WriteFile(
                  hPipeFromSrv, chResponse, nWritten - 1, NULL, &ovWrite);
               DWORD wErr = GetLastError();
               if (!wOk && wErr == ERROR_IO_PENDING)
               {
                  WaitForSingleObject(ovWrite.hEvent, 60000);
                  GetOverlappedResult(
                     hPipeFromSrv, &ovWrite, &cbBytesWritten, FALSE);
               }
               CloseHandle(ovWrite.hEvent);
            }
         }
         fprintf(stderr, "audacity-for-agents: pipe: client disconnected, listening again\n");
         fflush(stderr);
      }
      else
      {
         fprintf(stderr, "audacity-for-agents: pipe: connect incomplete "
            "(from=%i/%lu to=%i/%lu) — recycling instances\n",
            bConnectedFrom, errFrom, bConnectedTo, errTo);
         fflush(stderr);
         Sleep(50);
      }

      // Always tear down both instances so a half-open client cannot wedge
      // the next CreateFile (ERROR_PIPE_BUSY).
      CloseAgentsPipe(&hPipeToSrv);
      CloseAgentsPipe(&hPipeFromSrv);
   }
}

#else

#include <sys/types.h>
#include <sys/stat.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>

const char fifotmpl[] = "/tmp/audacity_for_agents_script_pipe.%s.%d";

const int nBuff = 1024;

extern "C" int DoSrv( char * pIn );
extern "C" int DoSrvMore( char * pOut, size_t nMax );

void PipeServer()
{
   FILE *fromFifo = NULL;
   FILE *toFifo = NULL;
   int rc;
   char buf[nBuff];
   char toFifoName[nBuff];
   char fromFifoName[nBuff];

   sprintf(toFifoName, fifotmpl, "to", getuid());
   sprintf(fromFifoName, fifotmpl, "from", getuid());

   unlink(toFifoName);
   unlink(fromFifoName);

   // TODO avoid symlink security issues?

   rc = mkfifo(fromFifoName, S_IRWXU) & mkfifo(toFifoName, S_IRWXU);
   if (rc < 0)
   {
      perror("Unable to create fifos");
      printf("Ignoring...");
//      return;
   }

   // open to (incoming) pipe first.  
   toFifo = fopen(toFifoName, "r");
   if (toFifo == NULL)
   {
      perror("Unable to open fifo to server from script");
      if (fromFifo != NULL)
         fclose(fromFifo);
      return;
   }

   // open from (outgoing) pipe second.  This could block if there is no reader.
   fromFifo = fopen(fromFifoName, "w");
   if (fromFifo == NULL)
   {
      perror("Unable to open fifo from server to script");
      fclose(toFifo);
      return;
   }

   while (fgets(buf, sizeof(buf), toFifo) != NULL)
   {
      int len = strlen(buf);
      if (len <= 1)
      {
         continue;
      }

      buf[len - 1] = '\0';

      printf("Server received %s\n", buf);
      DoSrv(buf);

      while (true)
      {
         len = DoSrvMore(buf, nBuff);
         if (len <= 1)
         {
            break;
         }
         printf("Server sending %s",buf);

         // len - 1 because we do not send the null character
         fwrite(buf, 1, len - 1, fromFifo);
      }
      fflush(fromFifo);
   }

   printf("Read failed on fifo, quitting\n");

   if (toFifo != NULL)
      fclose(toFifo);

   if (fromFifo != NULL)
      fclose(fromFifo);

   unlink(toFifoName);
   unlink(fromFifoName);
}
#endif
