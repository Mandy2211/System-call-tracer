#include <iostream>
#include <thread>
#include <vector>
#include <mutex>
#include <chrono>

// The single shared resource that all threads will "fight" over.
long long g_counter = 0;

// Only one thread can hold this lock at a time.
std::mutex g_mutex;

void worker_function(long iterations) {
    for (long i = 0; i < iterations; ++i) {
        // --- The Bottleneck is Here ---
        // 1. Acquire the lock. If another thread has it, this thread
        //    will be put to sleep by the OS kernel using a futex.
        g_mutex.lock();
        g_counter++;
        g_mutex.unlock();
        // --- End of Bottleneck ---
    }
}

int main(int argc, char* argv[]) {
    int num_threads = 8;
    long iterations_per_thread = 500000;

    if (argc == 3) {
        num_threads = std::stoi(argv[1]);
        iterations_per_thread = std::stol(argv[2]);
    }

    std::cout << "Starting lock contention demo..." << std::endl;
    std::cout << " - Threads: " << num_threads << std::endl;
    std::cout << " - Iterations per thread: " << iterations_per_thread << std::endl;
    std::cout << " - Total increments: " << (long long)num_threads * iterations_per_thread << std::endl;

    // --- Thread Creation ---
    std::vector<std::thread> threads;
    threads.reserve(num_threads);

    auto start_time = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_threads; ++i) {
        threads.emplace_back(worker_function, iterations_per_thread);
    }

    // --- Wait for all threads to finish ---
    for (auto& t : threads) {
        t.join();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;

    // --- Verification and Results ---
    std::cout << "\nAll threads finished." << std::endl;
    std::cout << "Final counter value: " << g_counter << " (Correct!)" << std::endl;
    std::cout << "Total execution time: " << elapsed.count() << " seconds" << std::endl;

    return 0;
}

