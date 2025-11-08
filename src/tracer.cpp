// tracer.cpp
#include <bits/stdc++.h>
#include <sys/ptrace.h>
#include <sys/types.h>    
#include <sys/wait.h> 
#include <sys/user.h> 
#include <sys/syscall.h>

#include <unistd.h>
#include <fcntl.h>  
#include <errno.h>   
#include <ctime>
#include <sys/stat.h>    
#include <time.h>   

#include "syscall_names.h" // provides SYSCALL_NAMES: unordered_map<long, string>

using namespace std;

struct SyscallStat {
    long count = 0; 
    long errors = 0;
    long long total_time_ns = 0; 
};

string now_iso() {
    char buf[64];
    time_t t = time(nullptr);
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", localtime(&t));
    return string(buf);
}

string syscall_name(long nr) {
    if (SYSCALL_NAMES.count(nr)) return SYSCALL_NAMES.at(nr);
    return string("sys_") + to_string(nr);
}

int main() {
    string dir, fname;
    cout << "Enter the directory of the file to be traced: ";
    if (!getline(cin, dir)) return 1;
    cout << "Enter the name of the file to be traced: ";
    if (!getline(cin, fname)) return 1;

    // Trim trailing spaces/newlines (simple)
    if (!dir.empty() && dir.back() == '\r') dir.pop_back();
    if (!fname.empty() && fname.back() == '\r') fname.pop_back();

    // Build full path (handle if user provided trailing slash)
    string fullpath;
    if (!dir.empty() && dir.back() == '/') fullpath = dir + fname;
    else fullpath = dir + "/" + fname;

    // Check file exists and is executable
    if (access(fullpath.c_str(), X_OK) != 0) {
        cerr << "Error: cannot access '" << fullpath << "' or not executable: " 
             << strerror(errno) << "\n";
        return 1;
    }

    // Prepare args for execvp (no extra args supported in this version)
    char* program = strdup(fullpath.c_str());
    char* args[] = { program, nullptr };

    // Fork + exec under ptrace
    pid_t child = fork();
    if (child == -1) {
        perror("fork");
        free(program);
        return 1;
    }

    if (child == 0) {
        // CHILD: ask kernel to let parent trace it
        if (ptrace(PTRACE_TRACEME, 0, nullptr, nullptr) == -1) {
            perror("ptrace(TRACEME)");
            _exit(1);
        }
        // stop ourselves to let parent set options
        kill(getpid(), SIGSTOP);
        // replace image
        execvp(program, args);
        // if execvp returns, it failed
        perror("execvp");
        _exit(127);
    }

    // PARENT: wait for child to stop
    int status;
    while (true) {
        pid_t w = waitpid(child, &status, 0);
        if (w == -1) {
            if (errno == EINTR) continue;
            perror("waitpid");
            free(program);
            return 1;
        }
        // child stopped
        break;
    }

    // Set ptrace options: get syscall stops marked with 0x80 (TRACESYSGOOD)
    long options = PTRACE_O_TRACESYSGOOD | PTRACE_O_EXITKILL;
    if (ptrace(PTRACE_SETOPTIONS, child, nullptr, (void*)options) == -1) {
        perror("ptrace(SETOPTIONS)");
        // continue anyway
    }

    // Prepare stats and state
    unordered_map<long, SyscallStat> stats;
    bool in_syscall = false;
    struct timespec entry_time{};
    long last_syscall = -1;

    // Prepare log + CSV with timestamped filenames
    string ts = now_iso();
    for (auto &c : ts) if (c == ':' || c == '-') c = '_';

    string datadir = "data";
    // create data/ if missing
    mkdir(datadir.c_str(), 0755);

    string logfile = datadir + "/tracer_" + ts + ".log";
    string csvfile  = datadir + "/syscalls_" + ts + ".csv";

    ofstream rawlog(logfile);
    ofstream csv(csvfile);

    if (!rawlog.is_open() || !csv.is_open()) {
        cerr << "Error: cannot open log files.\n";
        free(program);
        return 1;
    }

    csv << "syscall,syscall_nr,count,total_time_ns,avg_time_ns,errors\n";
    rawlog << "# tracer started: " << now_iso() << "\n";
    rawlog << "# tracing program: " << fullpath << " (pid=" << child << ")\n";

    // Main tracing loop
    while (true) {
        // Let child run until next syscall entry/exit (or signal/exit)
        if (ptrace(PTRACE_SYSCALL, child, nullptr, nullptr) == -1) {
            if (errno == ESRCH) break; // no such process
            perror("ptrace(SYSCALL)");
            break;
        }

        // Wait for child to stop
        pid_t w = waitpid(child, &status, 0);
        if (w == -1) {
            if (errno == EINTR) continue;
            perror("waitpid");
            break;
        }

        if (WIFEXITED(status)) {
            rawlog << "# child exited with status " << WEXITSTATUS(status) << "\n";
            break;
        }

        if (WIFSIGNALED(status)) {
            rawlog << "# child signaled with " << WTERMSIG(status) << "\n";
            break;
        }

        if (!WIFSTOPPED(status)) {
            // shouldn't normally happen; continue
            continue;
        }

        int sig = WSTOPSIG(status);

        // Check for a syscall-stop (TRACESYSGOOD sets 0x80)
        bool is_syscall_stop = (sig == (SIGTRAP | 0x80)) || (sig == SIGTRAP);

        if (!is_syscall_stop) {
            // Non-syscall stop (e.g., signal). Log and pass it through.
            rawlog << "# child stopped with signal " << sig << "\n";
            // Let the child continue and deliver the signal
            if (ptrace(PTRACE_SYSCALL, child, nullptr, (void*)(long)sig) == -1) {
                perror("ptrace(SYSCALL, deliver sig)");
                break;
            }
            continue;
        }

        // It's a syscall stop: get registers
        struct user_regs_struct regs;
        if (ptrace(PTRACE_GETREGS, child, nullptr, &regs) == -1) {
            rawlog << "ptrace(GETREGS) failed: " << strerror(errno) << "\n";
            continue;
        }

#ifdef __x86_64__
        long sc_nr = (long)regs.orig_rax;
        long retval = (long)regs.rax;
#elif defined(__aarch64__)
        long sc_nr = (long)regs.regs[8];
        long retval = (long)regs.regs[0];
#else
#error "Unsupported architecture"
#endif

        if (!in_syscall) {
            // syscall entry
            clock_gettime(CLOCK_MONOTONIC, &entry_time);
            last_syscall = sc_nr;
            in_syscall = true;

            rawlog << "ENTRY syscall=" << sc_nr
                   << " name=" << syscall_name(sc_nr) << "\n";
        } else {
            // syscall exit
            struct timespec exit_time;
            clock_gettime(CLOCK_MONOTONIC, &exit_time);

            long long delta = (exit_time.tv_sec - entry_time.tv_sec) * 1'000'000'000LL
                              + (exit_time.tv_nsec - entry_time.tv_nsec);

            SyscallStat &s = stats[last_syscall];
            s.count++;
            s.total_time_ns += delta;
            if (retval < 0) s.errors++;

            rawlog << "EXIT syscall=" << last_syscall
                   << " name=" << syscall_name(last_syscall)
                   << " retval=" << retval
                   << " time_ns=" << delta << "\n";

            in_syscall = false;
        }
    }

    // Dump summary to CSV
    for (auto &p : stats) {
        long nr = p.first;
        SyscallStat &s = p.second;
        long long avg = (s.count > 0) ? (s.total_time_ns / s.count) : 0;
        csv << syscall_name(nr) << ","
            << nr << ","
            << s.count << ","
            << s.total_time_ns << ","
            << avg << ","
            << s.errors << "\n";
    }

    rawlog << "# tracer finished: " << now_iso() << "\n";
    cout << "\nSummary written to " << csvfile << " and " << logfile << "\n";

    free(program);
    return 0;
}

