"""
Seed the database with sample news articles and generated cover images.

    python manage.py seed_news            # add content (idempotent by title)
    python manage.py seed_news --reset    # delete previously seeded posts first

All articles are original explainer-style sample content, not real news reports.
"""
import io
import random

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from blogs.models import Blog, Category

PALETTES = {
    'Technology': ((15, 23, 42), (30, 58, 138), (56, 189, 248)),
    'AI': ((46, 16, 101), (109, 40, 217), (244, 114, 182)),
    'Business': ((15, 40, 35), (20, 83, 75), (52, 211, 153)),
    'Sports': ((88, 28, 28), (185, 28, 28), (251, 146, 60)),
    'Science': ((15, 30, 50), (30, 80, 110), (94, 234, 212)),
    'Health': ((6, 78, 59), (13, 148, 136), (110, 231, 183)),
    'World': ((30, 27, 75), (67, 56, 202), (129, 140, 248)),
    'Entertainment': ((76, 29, 149), (190, 24, 93), (251, 113, 133)),
    'Politics': ((28, 28, 70), (70, 70, 160), (160, 160, 230)),
}

ARTICLES = [
    # ---------------------------------------------------------------- AI
    ('AI', 'How retrieval-augmented generation keeps chatbots honest',
     'RAG lets a language model look things up before it answers, cutting down on made-up facts.',
     "Large language models are trained on a snapshot of text, so they can be out of date and sometimes state wrong facts with confidence. Retrieval-augmented generation, or RAG, addresses this by adding a search step before the model writes its answer.\n\nWhen a question arrives, the system converts it into an embedding, a list of numbers that captures meaning, and finds the most similar passages in a document store. Those passages are pasted into the prompt, and the model is asked to answer using only that material. Because the sources are known, the answer can include citations that a reader can check.\n\nRAG is popular in customer support, internal knowledge bases and legal research because the documents can be updated without retraining the model. Its quality depends heavily on how the documents are split into chunks and how well the retriever ranks them, which is why many teams spend more time on search than on the model itself.", True),
    ('AI', 'Small language models are moving onto phones and laptops',
     'Compact models that run on-device promise lower latency, better privacy and no cloud bill.',
     "For years the trend in AI was simple: bigger models, better results. Now a second trend is catching up. Small language models with a few billion parameters can run directly on phones and laptops, thanks to techniques such as quantization, which stores weights in fewer bits, and distillation, where a small model learns from a larger one.\n\nRunning on-device has clear benefits. Responses start instantly because no network round trip is needed, private data such as messages and photos never leaves the device, and the feature keeps working offline. Developers also avoid paying per-request cloud costs.\n\nThe trade-off is capability. Small models are good at summarizing, rewriting and classifying, but they still struggle with long reasoning chains. Many products therefore use a hybrid approach, handling simple requests locally and sending harder ones to a larger cloud model.", False),
    ('AI', 'What developers should know before shipping an AI feature',
     'Evaluation, cost control and fallbacks matter more than the choice of model.',
     "Adding an AI feature to a product is easy to demo and hard to run well. The first lesson teams learn is that evaluation comes before everything else. A small, fixed set of real examples with expected outcomes lets you compare prompts and models objectively instead of relying on gut feeling.\n\nCost and latency are the next surprises. Long prompts, repeated calls and large models add up quickly, so caching results, trimming context and choosing the smallest model that passes your tests are standard practice.\n\nFinally, plan for failure. Models time out, rate limits hit and outputs sometimes come back malformed. A good feature degrades gracefully, for example by falling back to a rule-based answer, and never lets a bad response break the main user flow.", False),
    # ---------------------------------------------------------------- Technology
    ('Technology', 'Why passkeys are replacing passwords on major sites',
     'Passkeys use public-key cryptography to make phishing far harder than a typed password ever could.',
     "Passwords are weak because people reuse them and attackers can trick users into typing them into fake sites. Passkeys remove the shared secret entirely. When you create one, your device generates a key pair: the private key stays on the device and the public key is stored by the website.\n\nTo sign in, the site sends a challenge that only your private key can sign, usually after you confirm with a fingerprint, face scan or device PIN. Since the key is tied to the real website address, a look-alike phishing page simply cannot obtain a valid response.\n\nPasskeys can sync through a platform account, so losing a phone does not mean losing access. Adoption is still uneven, and many sites keep passwords as a fallback, but the direction of travel is clear.", True),
    ('Technology', 'Edge computing explained: moving the work closer to you',
     'Processing data near where it is created cuts delay and bandwidth for cameras, cars and factories.',
     "Traditional cloud computing sends data to a distant data center, processes it and sends the answer back. For many applications that round trip is too slow or too expensive. Edge computing places small servers or capable devices close to where data is produced.\n\nA factory camera that spots defects, a car that must brake in milliseconds, or a store that tracks inventory in real time all benefit from local processing. Only summaries or exceptions need to travel to the cloud, which saves bandwidth and keeps working even when the connection drops.\n\nEdge systems are harder to manage, since software must be updated across thousands of locations, but modern container tooling is making that practical.", False),
    ('Technology', 'The quiet rise of Rust in systems programming',
     'Memory safety without a garbage collector is winning Rust fans in browsers, operating systems and cloud tools.',
     "Many serious security bugs come from memory errors in languages like C and C++. Rust was designed to prevent them at compile time through ownership and borrowing rules, which guarantee that data is not used after it is freed or modified from two places at once.\n\nThe result is performance close to C with far fewer crashes and vulnerabilities. Large projects now use Rust for parts of browsers, operating system components, databases and command-line tools.\n\nThe learning curve is real: the compiler is strict and new developers often struggle with lifetimes. Teams report that the pain pays off later, because whole categories of bugs simply never reach production.", False),
    # ---------------------------------------------------------------- Business
    ('Business', 'How startups use unit economics to decide when to scale',
     'Customer acquisition cost versus lifetime value tells founders whether growth is healthy or just expensive.',
     "Fast growth can hide a broken business. Unit economics look at the profit or loss on a single customer to check whether the model works before more money is spent on marketing.\n\nTwo numbers matter most. Customer acquisition cost, or CAC, is what it takes to win one new customer. Lifetime value, or LTV, is the total margin that customer is expected to bring over time. A common rule of thumb is that LTV should be at least three times CAC, and that the CAC should be paid back within a year.\n\nIf the ratio is poor, scaling just multiplies losses. Founders then improve retention, raise prices or find cheaper channels before pushing harder on growth.", True),
    ('Business', 'Remote work is settling into a hybrid middle ground',
     'Most companies are landing on a few office days per week rather than a full return or fully remote model.',
     "After years of experimentation, many employers have settled on hybrid schedules, usually asking staff to come in two or three days a week. The aim is to keep the collaboration benefits of the office while preserving the flexibility workers say they value.\n\nThe approach brings new questions. Teams must coordinate so that people are in on the same days, offices need to be redesigned around meetings rather than rows of desks, and managers must judge performance by outcomes instead of visible hours.\n\nCompanies that communicate clear expectations tend to retain staff better than those that change policies abruptly. Flexibility has become a hiring advantage that is hard to take back.", False),
    ('Business', 'UPI and the growth of digital payments in India',
     'Instant bank-to-bank transfers have turned phones into wallets for street vendors and large retailers alike.',
     "The Unified Payments Interface, or UPI, lets people move money between bank accounts instantly using a simple address or a QR code. Because it works across banks and apps, a vendor needs only one code to accept payments from almost any customer.\n\nLow transaction costs and easy onboarding helped it reach small shops, taxi drivers and vegetable sellers who previously dealt only in cash. For consumers, splitting bills and paying utilities became a matter of seconds.\n\nChallenges remain, including fraud awareness, network reliability in remote areas and the question of how payment providers can earn sustainable revenue when most transfers are free. Other countries are now studying the model for their own systems.", False),
    # ---------------------------------------------------------------- Sports
    ('Sports', 'How data analytics is changing cricket strategy',
     'Ball-by-ball data now shapes batting orders, bowling plans and field placements.',
     "Cricket has always produced plenty of numbers, but ball-by-ball tracking has taken analysis to a new level. Teams study where a batter scores, which lengths trouble them and how their strike rate changes against spin or pace in different phases of the innings.\n\nBowlers use the same insight to plan: aim for a particular area against a particular opponent, then set the field to match. Captains lean on matchup data when deciding who bowls the tricky overs, while selectors compare players using consistent metrics rather than memory.\n\nCoaches stress that analytics supports rather than replaces instinct. The data points to a plan, but it is still the player who must execute it under pressure.", True),
    ('Sports', 'The science behind marathon training plans',
     'Gradual mileage, easy running and recovery weeks do more than heroic long runs.',
     "Most marathon plans share a few principles that sports scientists have supported for decades. The first is progressive overload: increase weekly distance gradually, often by no more than around ten percent, so bones and tendons can adapt.\n\nThe second is that most running should be easy. Slow runs build the aerobic base and leave the body fresh enough for the two or three harder sessions each week, such as intervals or tempo runs. A weekly long run teaches the body to burn fuel efficiently and prepares the mind for the distance.\n\nRecovery weeks, sleep and a short taper before race day matter just as much. Runners who skip them often arrive at the start line tired or injured.", False),
    ('Sports', 'Why esports is being treated like a traditional sport',
     'Professional teams now employ coaches, analysts, nutritionists and sports psychologists.',
     "Competitive gaming has grown from a hobby into a global industry with leagues, sponsors and large online audiences. Professional teams now run like traditional sports organizations, with structured practice schedules, video review and specialist coaches.\n\nPlayers face real physical demands too. Long hours at a desk bring wrist strain, back problems and eye fatigue, so many clubs add exercise programs, ergonomic setups and mental health support.\n\nCareers are short and the pressure is high, but the pathway is becoming clearer, with university scholarships, amateur circuits and official academies feeding talent into top-tier leagues.", False),
    # ---------------------------------------------------------------- Science
    ('Science', 'How the James Webb telescope sees through cosmic dust',
     'Infrared light passes through clouds that block visible light, revealing newborn stars and distant galaxies.',
     "Visible light is easily absorbed by clouds of gas and dust, which hide star-forming regions from ordinary telescopes. Infrared light has longer wavelengths and slips through much of that material, so an infrared observatory can look inside the clouds.\n\nThe James Webb Space Telescope carries a large segmented mirror and sits far from Earth, shielded from the Sun by a tennis-court-sized sunshield so its instruments stay extremely cold. Cold detectors are essential because warm objects glow in infrared and would drown out faint signals.\n\nIts images have revealed details of young star systems and some of the earliest galaxies, light from which has traveled for more than thirteen billion years.", True),
    ('Science', 'Why scientists are excited about solid-state batteries',
     'Replacing the liquid electrolyte could mean safer cells with more energy in the same space.',
     "Today's lithium-ion batteries use a liquid electrolyte to move ions between electrodes. That liquid is flammable and limits how much energy can be packed into a cell. Solid-state batteries replace it with a solid material, such as a ceramic or polymer.\n\nIn theory this allows a lithium metal anode, which stores more energy, and removes much of the fire risk. Charging could also be faster if the right materials are found.\n\nThe hurdles are manufacturing and durability. Solid layers can crack as the battery expands and contracts, and producing them cheaply at scale is difficult. Researchers and carmakers are running pilot lines, but widespread use is still some years away.", False),
    ('Science', 'Understanding CRISPR: gene editing in plain language',
     'A guide-and-scissors system lets scientists make precise changes to DNA.',
     "CRISPR began as a defense system in bacteria, which store snippets of virus DNA and use them to recognize and cut invaders. Scientists realized they could reprogram this system. A short guide RNA is designed to match a chosen stretch of DNA, and an enzyme called Cas9 acts like scissors at that spot.\n\nOnce the DNA is cut, the cell's own repair machinery fixes it, and researchers can use that process to disable a gene or insert a new sequence. The technique is faster and cheaper than earlier methods, which has accelerated research in agriculture and medicine.\n\nBecause changes to human embryos could be inherited, the technology raises serious ethical questions, and most countries tightly regulate its use.", False),
    # ---------------------------------------------------------------- Health
    ('Health', 'Sleep and learning: why students should protect their rest',
     'Memory consolidation happens during sleep, so cramming all night often backfires.',
     "While you sleep the brain replays the day's experiences and moves important information into long-term memory. Deep sleep and REM sleep both play a role, which is why a good night's rest after studying can improve recall more than extra hours spent awake.\n\nSleep deprivation reduces attention, slows reaction time and makes it harder to learn new material the next day. Teenagers and young adults often need around eight to ten hours, yet many get far less.\n\nSimple habits help: keep a regular bedtime, avoid screens and caffeine late in the evening, and keep the bedroom dark and cool. Short naps can also refresh focus without disturbing night sleep.", True),
    ('Health', 'Ultra-processed food: what the research does and does not say',
     'Studies link heavy intake with poorer health, but scientists are still working out why.',
     "Ultra-processed foods include packaged snacks, sweet drinks, instant meals and many ready-to-eat products made with additives and refined ingredients. Large observational studies associate high consumption with weight gain and several chronic conditions.\n\nThe evidence is not simple. These foods are often high in sugar, salt and refined fat, and they tend to be easy to overeat, so it is hard to separate the effect of processing from the effect of nutrients. Some processed foods, such as wholegrain bread or yogurt, can be part of a healthy diet.\n\nNutrition experts generally suggest building meals around vegetables, fruit, pulses and whole grains and treating packaged snacks as occasional extras.", False),
    ('Health', 'How wearable devices track health, and their limits',
     'Smartwatches measure heart rate and activity well, but they are not diagnostic tools.',
     "Wearables use optical sensors that shine light into the skin and measure how much is absorbed as blood pulses, which gives an estimate of heart rate. Motion sensors count steps and detect workouts, and some models add skin temperature or blood oxygen readings.\n\nThe data is useful for spotting trends, such as improving fitness or irregular sleep. Some devices can flag an irregular heart rhythm so that a user can seek a proper check-up.\n\nAccuracy varies with fit, skin tone and movement, and a watch cannot replace a medical examination. Doctors advise using the numbers as a prompt for questions rather than as a diagnosis.", False),
    # ---------------------------------------------------------------- World
    ('World', 'How climate adaptation is reshaping coastal cities',
     'From sea walls to sponge parks, planners are preparing for heavier rain and rising seas.',
     "Cities on coasts and rivers face more frequent flooding as sea levels rise and storms deliver more rain in a short time. Alongside efforts to cut emissions, planners are investing in adaptation, the work of living with the changes already underway.\n\nEngineered defenses such as sea walls and pumps are part of the answer, but many cities are also turning to nature-based solutions. Wetlands absorb storm surge, permeable pavements and parks act like sponges, and trees reduce heat in dense neighborhoods.\n\nFunding and fairness are major challenges, since low-income areas are often the most exposed. Successful plans involve residents early and combine long-term infrastructure with practical steps like early-warning systems.", True),
    ('World', 'The global race to build renewable energy storage',
     'Batteries, pumped hydro and other tools are needed to keep the lights on when the sun sets.',
     "Solar and wind power are now among the cheapest sources of new electricity, but they produce energy only when the sun shines or the wind blows. Storage fills the gap by saving surplus power and releasing it when demand rises.\n\nGrid-scale batteries respond within seconds and are being installed rapidly. Pumped hydro, which moves water uphill and releases it through turbines, offers long-duration storage but needs suitable geography. Researchers are also testing options such as compressed air, thermal storage and hydrogen.\n\nGrid operators say a mix of technologies, together with better transmission lines and flexible demand, will be required to run on high shares of renewables.", False),
    ('World', 'Why water-saving farming matters in a warming world',
     'Drip irrigation, soil sensors and drought-tolerant crops help farmers grow more with less.',
     "Agriculture uses most of the world's fresh water, and changing rainfall patterns are putting pressure on farmers. Efficient irrigation is one of the most effective responses. Drip systems deliver water directly to roots, wasting far less than flooding a field.\n\nSoil moisture sensors and weather forecasts help farmers water only when needed, and mulching keeps moisture in the ground. Plant breeders are developing crops that tolerate heat and drought, while traditional practices such as rainwater harvesting are being revived.\n\nCost remains a barrier for small farms, so training, shared equipment and affordable loans are just as important as the technology itself.", False),
    # ---------------------------------------------------------------- Entertainment
    ('Entertainment', 'How streaming recommendations decide what you watch next',
     'Collaborative filtering and viewing signals quietly shape your home screen.',
     "Streaming services rely on recommendation systems to help viewers choose from thousands of titles. The classic approach, collaborative filtering, finds people with similar viewing histories and suggests what they enjoyed. Content-based methods compare details such as genre, cast and mood.\n\nModern systems blend many signals, including what you finish, what you abandon, the time of day and the device you use. Even the artwork shown for a title can be personalized to match your tastes.\n\nCritics note that algorithms can create filter bubbles and favor familiar content, so some platforms add human-curated rows and diversity rules to keep discovery varied.", True),
    ('Entertainment', 'Why indie games keep punching above their weight',
     'Small teams are winning players with strong ideas, distinct art and tight design.',
     "Independent games are often made by teams of a handful of people, yet they regularly earn awards and loyal communities. Without large budgets they focus on a single strong idea, a distinct visual style and mechanics that are easy to learn and hard to master.\n\nDigital storefronts and accessible engines have lowered the barrier to publishing, and social media lets small studios build an audience during development. Early access releases let players shape the game with feedback.\n\nThe risks are real, since many projects struggle to be noticed, but a memorable hit can launch a studio and influence the wider industry.", False),
    ('Entertainment', 'The return of live music and the economics of touring',
     'Rising costs and ticket demand are changing how artists plan tours.',
     "Live concerts have rebounded strongly, with fans willing to travel for shows. For artists, touring is now a major source of income as streaming pays small amounts per play.\n\nBut running a tour is expensive. Crew wages, transport, venue fees and production all add up, and smaller acts can struggle to break even. Many choose shorter routes, regional festivals or residencies in a single city to cut costs.\n\nFans, in turn, face higher ticket prices and fees, which has prompted debate about transparency. Artists increasingly use direct mailing lists and fan clubs to sell tickets and merchandise on fairer terms.", False),
]


def make_cover(category, title):
    pal = PALETTES.get(category, ((20, 25, 35), (50, 60, 80), (140, 160, 190)))
    c_dark, c_mid, c_accent = pal
    w, h = 1200, 630
    img = Image.new('RGB', (w, h), c_dark)
    px = img.load()
    for y in range(h):
        for x in range(w):
            factor = (x / w) * 0.55 + (y / h) * 0.45
            r = int(c_dark[0] + (c_mid[0] - c_dark[0]) * factor)
            g = int(c_dark[1] + (c_mid[1] - c_dark[1]) * factor)
            b = int(c_dark[2] + (c_mid[2] - c_dark[2]) * factor)
            px[x, y] = (r, g, b)

    rnd = random.Random(title)
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gx = rnd.randint(int(w * 0.4), int(w * 0.85))
    gy = rnd.randint(int(h * 0.2), int(h * 0.8))
    gr = rnd.randint(220, 380)
    for i in range(12):
        rad = gr - i * (gr // 12)
        alpha = int(12 + i * 4)
        gdraw.ellipse((gx - rad, gy - rad, gx + rad, gy + rad), fill=(c_accent[0], c_accent[1], c_accent[2], alpha))

    beam = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(beam)
    bx = rnd.randint(int(w * 0.25), int(w * 0.7))
    bdraw.polygon([(bx, 0), (bx + 280, 0), (bx - 120, h), (bx - 400, h)], fill=(c_accent[0], c_accent[1], c_accent[2], 22))

    geom = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(geom)
    cx, cy = rnd.randint(int(w * 0.55), int(w * 0.9)), rnd.randint(int(h * 0.2), int(h * 0.8))
    for r_ring in [120, 200, 300, 420]:
        draw.ellipse((cx - r_ring, cy - r_ring, cx + r_ring, cy + r_ring), outline=(255, 255, 255, 28), width=2)

    dot_start_x = rnd.randint(60, 200)
    dot_start_y = rnd.randint(60, 200)
    for xi in range(6):
        for yi in range(5):
            dx = dot_start_x + xi * 28
            dy = dot_start_y + yi * 28
            draw.ellipse((dx - 2, dy - 2, dx + 2, dy + 2), fill=(255, 255, 255, 45))

    img = Image.alpha_composite(img.convert('RGBA'), glow)
    img = Image.alpha_composite(img, beam)
    img = Image.alpha_composite(img, geom)
    img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = 'Seed sample news articles with generated cover images'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete posts created by this command first')

    def handle(self, *args, **opts):
        author = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not author:
            author = User.objects.create_user('newsdesk', password='newsdesk12345')
            self.stdout.write('Created user "newsdesk" (password: newsdesk12345)')
        titles = [a[1] for a in ARTICLES]
        if opts['reset']:
            Blog.objects.filter(title__in=titles).delete()
        created = 0
        for category, title, desc, body, featured in ARTICLES:
            cat, _ = Category.objects.get_or_create(category_name=category)
            if Blog.objects.filter(title=title).exists():
                continue
            post = Blog(title=title, category=cat, author=author, short_description=desc,
                        blog_body=body, status='Published', is_featured=featured)
            post.featured_image.save(f'{category.lower()}-{created}.jpg', make_cover(category, title), save=False)
            post.save()
            created += 1
        # spread some view counts so "Trending" looks realistic
        rnd = random.Random(7)
        for post in Blog.objects.filter(title__in=titles):
            if post.views == 0:
                Blog.objects.filter(pk=post.pk).update(views=rnd.randint(20, 900))
        self.stdout.write(self.style.SUCCESS(f'Seeded {created} new articles ({len(ARTICLES)} total available).'))
